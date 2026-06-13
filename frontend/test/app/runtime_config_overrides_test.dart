import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/src/app/config/runtime_config_overrides.dart';

void main() {
  group('RuntimeConfigOverrides', () {
    test('uses explicit override values before stored values', () {
      const overrides = RuntimeConfigOverrides(
        backendHost: '192.168.1.10',
        backendPort: '8899',
        serviceToken: 'override-token',
        spaceSlug: 'team-space',
        memoryScopeExternalRef: 'crm',
      );

      expect(overrides.resolveBackendHost('127.0.0.1'), '192.168.1.10');
      expect(overrides.resolveBackendPort(7788), 8899);
      expect(overrides.resolveServiceToken('stored-token'), 'override-token');
      expect(overrides.resolveSpaceSlug('default'), 'team-space');
      expect(overrides.resolveMemoryScopeExternalRef('default'), 'crm');
    });

    test('falls back to stored values when overrides are empty or invalid', () {
      const overrides = RuntimeConfigOverrides(
        backendHost: ' ',
        backendPort: '70000',
        serviceToken: '',
        spaceSlug: '',
        memoryScopeExternalRef: '',
      );

      expect(overrides.resolveBackendHost('127.0.0.1'), '127.0.0.1');
      expect(overrides.resolveBackendPort(7788), 7788);
      expect(overrides.resolveServiceToken('stored-token'), 'stored-token');
      expect(overrides.resolveSpaceSlug('default'), 'default');
      expect(overrides.resolveMemoryScopeExternalRef('default'), 'default');
    });
  });
}
