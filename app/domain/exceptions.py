class ItsmError(Exception): """Base for every business error."""
class ValidationError(ItsmError): pass
class AuthenticationError(ItsmError): pass
class AuthorizationError(ItsmError): pass
class NotFoundError(ItsmError): pass
class InvalidTransitionError(ItsmError): pass
class TechnicianUnavailableError(ItsmError): pass
class DuplicateIncidentError(ItsmError): pass
class MissingSlaError(ItsmError): pass
class PersistenceError(ItsmError): pass
