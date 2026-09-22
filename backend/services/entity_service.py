"""Validate and commit entity writes together with their derived route graph."""

from pydantic import BaseModel

from backend.exceptions import AppError, ConflictError, NotFoundError
from backend.models import PROTECTED_FIELDS
from backend.services.environment_service import EnvironmentService
from core.models import AirRoute, Mission
from core.repository import RepositoryRegistry
from simulation.environment.route_network import RouteNetwork


class EntityService:
    def __init__(self, registry: RepositoryRegistry, environment: EnvironmentService):
        self.registry = registry
        self.environment = environment

    def _require_reference(self, repo_name: str, item_id: str) -> None:
        if not getattr(self.registry, repo_name).exists(item_id):
            raise AppError(422, "invalid_reference", f"{repo_name}: {item_id} does not exist")

    def _validate(self, entity: BaseModel) -> None:
        if isinstance(entity, Mission):
            self._require_reference("aircraft", entity.aircraft_id)
            if entity.route_id is not None:
                self._require_reference("routes", entity.route_id)
        elif isinstance(entity, AirRoute):
            sequence = entity.waypoint_ids or [entity.start, entity.end]
            if len(sequence) < 2 or sequence[0] != entity.start or sequence[-1] != entity.end:
                raise AppError(422, "invalid_route", "waypoint_ids must include start and end in order")
            if entity.start == entity.end or any(a == b for a, b in zip(sequence, sequence[1:])):
                raise AppError(422, "invalid_route", "route endpoints and adjacent waypoints must differ")
            for waypoint_id in sequence:
                self._require_reference("waypoints", waypoint_id)
            positions = [self.registry.waypoints.get(item_id).position for item_id in sequence]
            entity.distance = sum(a.distance_to(b) for a, b in zip(positions, positions[1:]))
            if entity.distance <= 0:
                raise AppError(422, "invalid_route", "route must have positive length")

    def _require_unreferenced(self, repo_name: str, item_id: str) -> None:
        dependencies = []
        if repo_name in {"aircraft", "routes"}:
            field = "aircraft_id" if repo_name == "aircraft" else "route_id"
            dependencies = [m.id for m in self.registry.missions.list() if getattr(m, field) == item_id]
        elif repo_name == "waypoints":
            dependencies = [r.id for r in self.registry.routes.list()
                            if item_id in (r.waypoint_ids or [r.start, r.end])]
        if dependencies:
            raise AppError(409, "resource_in_use", "Remove dependent entities before deleting this resource",
                           {"dependents": dependencies})

    def write(self, repo_name: str, model_type: type[BaseModel], payload: BaseModel,
              item_id: str | None = None) -> BaseModel:
        """PUT replaces writable fields; omitted ID uses path ID; stored internal fields survive."""
        registry = self.registry
        repo = getattr(registry, repo_name)
        with registry.lock:
            with registry.transaction():
                previous = None
                if item_id is not None:
                    if not repo.exists(item_id):
                        raise NotFoundError(repo_name, item_id)
                    if "id" in payload.model_fields_set and payload.id != item_id:
                        raise AppError(422, "id_mismatch", "Body ID must equal path ID")
                    previous = repo.get(item_id)
                    if repo_name == "events" and previous.handled:
                        raise ConflictError("A handled event cannot be edited")

                values = payload.model_dump(exclude={"altitude"})
                if item_id is not None:
                    values["id"] = item_id
                    for field in PROTECTED_FIELDS.get(repo_name, set()):
                        values[field] = getattr(previous, field)
                elif values.get("id") is None:
                    values.pop("id", None)
                entity = model_type.model_validate(values)
                self._validate(entity)
                if item_id is None:
                    if repo.exists(entity.id):
                        raise ConflictError(f"{repo_name} already exists: {entity.id}")
                    result = repo.add(entity)
                else:
                    result = repo.update(entity)

                network = self._build_network(repo_name)
            if network is not None:
                self.environment.network = network
                self.environment.version += 1
            return result

    def delete(self, repo_name: str, item_id: str) -> None:
        registry = self.registry
        repo = getattr(registry, repo_name)
        with registry.lock:
            with registry.transaction():
                if not repo.exists(item_id):
                    raise NotFoundError(repo_name, item_id)
                self._require_unreferenced(repo_name, item_id)
                if repo_name == "events" and repo.get(item_id).handled:
                    raise ConflictError("A handled event is an immutable audit record")
                repo.delete(item_id)
                network = self._build_network(repo_name)
            if network is not None:
                self.environment.network = network
                self.environment.version += 1

    def _build_network(self, changed_repo: str) -> RouteNetwork | None:
        if changed_repo not in {"waypoints", "routes"}:
            return None
        # Recompute lengths after waypoint moves, without regenerating buildings.
        for route in self.registry.routes.list():
            self._validate(route)
            self.registry.routes.update(route)
        return RouteNetwork.build(self.registry.waypoints.list(), self.registry.routes.list())
