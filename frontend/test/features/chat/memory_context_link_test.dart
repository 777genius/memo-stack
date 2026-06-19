import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/src/features/chat/domain/entities/memory_context_link.dart';

void main() {
  group('MemoryContextLinkSuggestion', () {
    test('normalizes dedupe review metadata into signals and actions', () {
      final suggestion = MemoryContextLinkSuggestion.fromMap({
        'id': 'ctxlinksug-duplicate',
        'space_id': 'space-1',
        'memory_scope_id': 'scope-1',
        'source_type': 'asset',
        'source_id': 'asset-duplicate',
        'target_type': 'asset',
        'target_id': 'asset-source',
        'relation_type': 'duplicates',
        'confidence': 'high',
        'reason': 'Exact same asset bytes already exist',
        'score': 100,
        'status': 'pending',
        'metadata': {
          'source_label': 'copy.png',
          'target_label': 'original.png',
          'reason_codes': ['exact_sha256'],
          'dedupe_reason_codes': [
            'exact_sha256',
            'same_memory_scope',
            'blob_reused',
          ],
          'dedupe_match_type': 'exact_sha256',
          'recommended_action': 'link_duplicate_asset_contexts',
        },
        'created_at': '2026-06-20T10:00:00Z',
        'updated_at': '2026-06-20T10:00:00Z',
      });

      expect(suggestion.sourceLabel, 'copy.png');
      expect(suggestion.targetLabel, 'original.png');
      expect(suggestion.dedupeMatchType, 'exact_sha256');
      expect(suggestion.reasonCodes, [
        'exact_sha256',
        'same_memory_scope',
        'blob_reused',
      ]);
      expect(suggestion.reasonSignalLabels, [
        'exact duplicate',
        'same scope',
        'blob reused',
      ]);
      expect(suggestion.recommendedActionLabel, 'link duplicate contexts');
    });
  });
}
