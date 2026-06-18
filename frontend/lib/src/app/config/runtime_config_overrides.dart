class RuntimeConfigOverrides {
  static const _defaultBackendHostDefine = 'INFINITY_CONTEXT_BACKEND_HOST';
  static const _defaultBackendPortDefine = 'INFINITY_CONTEXT_BACKEND_PORT';
  static const _defaultServiceTokenDefine = 'INFINITY_CONTEXT_SERVICE_TOKEN';
  static const _defaultSpaceSlugDefine = 'INFINITY_CONTEXT_SPACE_SLUG';
  static const _defaultMemoryScopeDefine = 'INFINITY_CONTEXT_MEMORY_SCOPE';

  final String backendHost;
  final String backendPort;
  final String serviceToken;
  final String spaceSlug;
  final String memoryScopeExternalRef;

  const RuntimeConfigOverrides({
    this.backendHost = '',
    this.backendPort = '',
    this.serviceToken = '',
    this.spaceSlug = '',
    this.memoryScopeExternalRef = '',
  });

  const RuntimeConfigOverrides.fromDartDefines()
      : backendHost = const String.fromEnvironment(_defaultBackendHostDefine),
        backendPort = const String.fromEnvironment(_defaultBackendPortDefine),
        serviceToken = const String.fromEnvironment(_defaultServiceTokenDefine),
        spaceSlug = const String.fromEnvironment(_defaultSpaceSlugDefine),
        memoryScopeExternalRef = const String.fromEnvironment(
          _defaultMemoryScopeDefine,
        );

  String? resolveBackendHost(String? stored) => _text(backendHost) ?? stored;

  int? resolveBackendPort(int? stored) => _port(backendPort) ?? stored;

  String? resolveServiceToken(String? stored) => _text(serviceToken) ?? stored;

  String? resolveSpaceSlug(String? stored) => _text(spaceSlug) ?? stored;

  String? resolveMemoryScopeExternalRef(String? stored) =>
      _text(memoryScopeExternalRef) ?? stored;

  String? _text(String value) {
    final trimmed = value.trim();
    return trimmed.isEmpty ? null : trimmed;
  }

  int? _port(String value) {
    final parsed = int.tryParse(value.trim());
    if (parsed == null || parsed < 1 || parsed > 65535) {
      return null;
    }
    return parsed;
  }
}
