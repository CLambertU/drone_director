"""Seeded initial conditions and timed disturbances; all outcomes are simulated."""

import math
import random

from core.models import (Aircraft, AirRoute, CityConfig, Event, EventType, GeoPoint,
                         Mission, Position3D, Severity, Waypoint, WaypointType)
from simulation.aircraft.flight import FlightPlan
from simulation.environment.builder import rectangle_polygon


def prepare_demo(engine, aircraft_count=100, seed=42):
    if not 2 <= aircraft_count <= 500:
        raise ValueError("演示飞行器数量须为 2 至 500")
    if engine.running:
        raise RuntimeError("请先暂停再生成演示场景")
    rng = random.Random(seed)
    rows = max(2, math.ceil(aircraft_count/4))
    config = CityConfig(name="天枢试验城区", origin=GeoPoint(latitude=30.5728, longitude=104.0668),
        min_x=0, min_y=0, max_x=4000, max_y=max(1200, 400+rows*150),
        grid_resolution=40, building_seed=seed)
    waypoints, routes, aircraft, missions = {}, [], [], []

    def point(key, x, y, z, kind=WaypointType.WAYPOINT, capacity=8):
        waypoints[key] = Waypoint(id=key, name=key, position=Position3D(x=x,y=y,z=z),
                                 type=kind, capacity=capacity, risk_level=0.1)
        return key

    def edge(a,b):
        routes.append(AirRoute(id=f"R-{a}-{b}", name=f"{a} ↔ {b}", start=a, end=b,
            waypoint_ids=[a,b], distance=waypoints[a].position.distance_to(waypoints[b].position),
            capacity=8, risk_level=0.1))

    xs = [200,800,1400,2000,3600]
    for row in range(rows):
        y = 200+row*150
        for layer,z in enumerate((150,210)):
            for col,x in enumerate(xs):
                key=point(f"L{layer}Y{row}X{col}",x,y,z)
                if col: edge(f"L{layer}Y{row}X{col-1}",key)
                if row: edge(f"L{layer}Y{row-1}X{col}",key)
                if layer: edge(f"L0Y{row}X{col}",key)
        for offset in range(4):
            index=row*4+offset
            if index>=aircraft_count: break
            destination_y=y+(offset-1.5)*34
            approach=point(f"AP{index}",3800,destination_y,150)
            destination=point(f"PAD{index}",3800,destination_y,0,WaypointType.VERTIPORT,1)
            edge(f"L0Y{row}X4",approach)
            edge(approach,destination)
            origin=waypoints[f"L0Y{row}X{offset}"].position
            drone=Aircraft(id=f"UAV-{index+1:03d}",name=f"天枢 {index+1:03d}",position=origin.model_copy(),
                           battery=round(rng.uniform(0.8,1.0),3),priority=rng.randint(0,8))
            aircraft.append(drone)
            missions.append(Mission(id=f"MISSION-{index+1:03d}",aircraft_id=drone.id,
                origin=origin.model_copy(),destination=waypoints[destination].position.model_copy(),priority=drone.priority))
        if row%4==0:
            approach=point(f"EB-APP-{row}",2200,y+70,150)
            bay=point(f"EB-{row}",2200,y+70,0,WaypointType.EMERGENCY_BAY,1)
            edge(f"L0Y{row}X3",approach)
            edge(approach,bay)
    staged=type(engine.environment)()
    with engine.registry.transaction():
        engine.registry.reset()
        for name,items in (("waypoints",waypoints.values()),("routes",routes),("aircraft",aircraft),("missions",missions)):
            for item in items: getattr(engine.registry,name).add(item)
        staged.apply_seed(config,None,engine.registry)
        engine.registry.set_metadata("environment", {"city_config":config.model_dump(mode="json"),
            "buildings":[b.model_dump(mode="json") for b in staged.city.buildings]})
    engine.environment.install_from(staged)
    engine.reset_runtime()
    engine.demo_enabled=True
    engine._schedule()
    engine._record(Event(type=EventType.INFO,description=f"随机种子 {seed}：已生成 {aircraft_count} 架飞行器及任务",
                         result={"seed":seed,"aircraft_count":aircraft_count}))


def advance_demo(engine):
    if not engine.demo_enabled:
        return
    if engine.demo_stage==0 and engine.time_s>=20:
        route=max(engine.routes.values(),key=lambda r:(engine.occupancy.get(r.id,0),r.id))
        engine.inject_event(Event(type=EventType.ROUTE_CONGESTION,related_id=route.id,severity=Severity.WARNING,
            description="演示事件 1：航路容量下降，重新分配流量",payload={"capacity":1}))
        engine.demo_stage=1
    elif engine.demo_stage==1 and engine.time_s>=45:
        cfg=engine.environment.city.config
        area=rectangle_polygon(2900,cfg.height*0.55,450,min(700,cfg.height*0.3))
        weather_event=engine.inject_event(Event(type=EventType.WEATHER,severity=Severity.CRITICAL,
            description="演示事件 2：东部雷暴，动态更新禁入区域并重规划",
            payload={"affected_area":area.model_dump(),"wind_speed":22,"visibility_m":1200,"precipitation":"thunderstorm"}))
        engine.demo_weather_id=weather_event.result["weather_id"]
        engine.demo_stage=2
    elif engine.demo_stage==2 and engine.time_s>=70:
        available=[a for a in engine.aircraft.values() if a.id in engine.plans and not engine.plans[a.id].complete]
        if available:
            bays=[w for w in engine.waypoints.values() if w.type==WaypointType.EMERGENCY_BAY]
            victim=min(available,key=lambda a:min(a.position.distance_to(b.position) for b in bays))
            engine.inject_event(Event(type=EventType.AIRCRAFT_FAILURE,related_id=victim.id,severity=Severity.EMERGENCY,
                description="演示事件 3：动力故障，搜索可达备降点",payload={"range_derating":0.55}))
        engine.demo_stage=3
    elif engine.demo_stage==3 and engine.time_s>=95:
        _crossing_intents(engine)
        engine.demo_stage=4
    if engine.demo_stage==4 and engine.time_s>=160 and engine.demo_weather_id in engine.weather:
        expired=engine.weather.pop(engine.demo_weather_id)
        from core.models import RouteStatus
        from simulation.environment.route_network import RouteNetwork
        for route in engine.routes.values():
            if route.status != RouteStatus.RESTRICTED:
                continue
            nodes=route.waypoint_ids or [route.start,route.end]
            intersects=any(expired.affected_area.intersects_segment(
                engine.waypoints[a].position.xy,engine.waypoints[b].position.xy)
                for a,b in zip(nodes,nodes[1:]))
            other_weather=any(any(w.affected_area.intersects_segment(
                engine.waypoints[a].position.xy,engine.waypoints[b].position.xy)
                for a,b in zip(nodes,nodes[1:])) for w in engine.weather.values())
            if intersects and not other_weather and not any(r.active and any(r.polygon.intersects_prism(
                engine.waypoints[a].position,engine.waypoints[b].position,r.min_altitude,r.max_altitude)
                for a,b in zip(nodes,nodes[1:])) for r in engine.restrictions.values()):
                route.status=RouteStatus.OPEN
        engine.environment.network=RouteNetwork.build(engine.waypoints.values(),engine.routes.values())
        engine.environment.version+=1
        engine._record(Event(type=EventType.INFO,description="演示雷暴消散，恢复受影响航路并继续调度",
                             result={"weather_id":expired.id,"affected_area":expired.affected_area.model_dump()}))
        engine._schedule()
    if engine.demo_stage==4 and engine.time_s>=220 and not engine.demo_complete:
        engine.demo_complete=True
        engine._record(Event(type=EventType.INFO,description="四类演示扰动已执行，运行指标已记录；剩余任务继续飞行",
            result={"demo_events_finished":True,"resolved_conflicts":engine.resolved_conflicts}))
        engine.checkpoint()
    if engine.demo_stage==4 and engine.time_s>=220:
        from core.models import MissionStatus
        terminal={MissionStatus.COMPLETED,MissionStatus.DIVERTED,MissionStatus.FAILED}
        if all(m.status in terminal for m in engine.missions.values()) or engine.time_s>=600:
            engine.running=False
            engine._record(Event(type=EventType.INFO,description="自动演示停止；未完成任务保留当前状态供检查",
                result={"completed":sum(m.status==MissionStatus.COMPLETED for m in engine.missions.values()),
                        "diverted":sum(m.status==MissionStatus.DIVERTED for m in engine.missions.values()),
                        "failed":sum(m.status==MissionStatus.FAILED for m in engine.missions.values()),
                        "pending":sum(m.status not in terminal for m in engine.missions.values())}))
            engine.checkpoint()
            return False


def _crossing_intents(engine):
    """Change two flight intents through a shared point, without moving aircraft positions."""
    from simulation.engine.safety import feasible
    active=[a for a in engine.aircraft.values() if a.id in engine.plans and not engine.plans[a.id].complete
            and not engine.plans[a.id].emergency_bay and a.position.z>=140]
    choices=[]
    for i,a in enumerate(active):
        for b in active[i+1:]:
            distance=a.position.distance_to(b.position)
            if 60<distance<400 and abs(a.position.z-b.position.z)<1:
                choices.append((distance,a.id,b.id))
    for _,a_id,b_id in sorted(choices):
        a,b=engine.aircraft[a_id],engine.aircraft[b_id]
        meeting=Position3D(x=(a.position.x+b.position.x)/2+120,
                          y=(a.position.y+b.position.y)/2,z=a.position.z)
        pa=FlightPlan([a.position.model_copy(),meeting,*engine.plans[a_id].positions[engine.plans[a_id].cursor:]],[],speed_mps=15)
        pb=FlightPlan([b.position.model_copy(),meeting,*engine.plans[b_id].positions[engine.plans[b_id].cursor:]],[],speed_mps=15)
        if feasible(engine,a,pa) and feasible(engine,b,pb):
            engine.plans[a_id],engine.plans[b_id]=pa,pb
            engine._record(Event(type=EventType.INFO,description="演示事件 4：两机任务意图出现交汇，交由预测检测与解脱",
                result={"aircraft_a":a_id,"aircraft_b":b_id,"meeting_point":meeting.model_dump()}))
            return
    engine.alert("demo", "当前场景没有可安全构造交汇意图的两架飞机；未伪造冲突结果")
