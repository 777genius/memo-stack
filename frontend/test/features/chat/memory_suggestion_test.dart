import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/src/features/chat/domain/entities/memory_suggestion.dart';

void main() {
  group('MemorySuggestion', () {
    test('parses duplicate merge review contract', () {
      final suggestion = MemorySuggestion.fromMap({
        'id': 'sug-duplicate',
        'space_id': 'space-1',
        'memory_scope_id': 'scope-1',
        'candidate_text': 'Docs retrieval should use Qdrant vectors.',
        'kind': 'note',
        'operation': 'review',
        'status': 'pending',
        'confidence': 'medium',
        'trust_level': 'medium',
        'safe_reason': 'candidate matches an active fact',
        'target_fact_id': 'fact-1',
        'target_fact_version': 1,
        'review_kind': 'duplicate_fact_merge',
        'review_actionable': true,
        'available_review_actions': [
          'approve',
          'reject',
          'expire',
          'resolve_duplicate',
        ],
        'review_resolution_options': [
          {
            'id': 'merge_source_refs',
            'review_action': 'resolve_duplicate',
            'effect': 'merge_source_refs_into_existing_fact',
            'availability': 'available',
            'resolution_action': 'merge_source_refs',
          },
          {
            'id': 'keep_separate_fact',
            'review_action': 'resolve_duplicate',
            'effect': 'create_new_fact_keep_existing_fact',
            'availability': 'available',
            'resolution_action': 'keep_separate_fact',
          },
        ],
        'review_payload': {
          'recommended_action': 'merge_source_refs_into_existing_fact',
          'default_resolution': 'merge_or_keep_separate_after_review',
        },
        'created_at': '2026-06-20T10:00:00Z',
        'updated_at': '2026-06-20T10:00:00Z',
      });

      expect(suggestion.isPending, true);
      expect(suggestion.isDuplicateMergeReview, true);
      expect(suggestion.canResolveDuplicate, true);
      expect(suggestion.reviewTitle, 'Duplicate memory');
      expect(
          suggestion.recommendedAction, 'merge_source_refs_into_existing_fact');
      expect(
          suggestion.defaultResolution, 'merge_or_keep_separate_after_review');
      expect(suggestion.reviewResolutionOptions.first.label, 'Merge sources');
      expect(suggestion.reviewResolutionOptions[1].label, 'Keep separate');
    });
  });
}
