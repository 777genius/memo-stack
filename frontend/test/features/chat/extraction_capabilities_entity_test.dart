import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/src/features/chat/domain/entities/attachment_extraction_plan.dart';
import 'package:frontend/src/features/chat/domain/entities/extraction_capabilities.dart';

void main() {
  group('ExtractionCapabilities', () {
    test('parses provider contract diagnostics without raw API assumptions',
        () {
      final capabilities = ExtractionCapabilities.fromMap({
        'enabled': true,
        'default_profile': 'standard_local',
        'profiles_v2': [
          {
            'name': 'media_api',
            'enabled': false,
            'status': 'blocked',
            'reason': 'external AI disabled',
            'providers': ['openai_transcription'],
            'input_modalities': ['audio', 'video'],
            'evidence_coordinates': ['time_range_ms', 'bbox'],
            'primary_artifact_types': ['transcript', 'keyframe'],
            'transcript_features': ['segments', 'time_ranges'],
            'video_features': ['ffprobe_metadata', 'sampled_keyframes'],
            'external_provider_egress': true,
            'requires_explicit_external_ai': true,
            'artifact_payloads_bounded': true,
          },
        ],
        'providers': {
          'openai_transcription': {
            'kind': 'asr',
            'installed': true,
            'configured': false,
            'enabled': false,
            'status': 'blocked',
            'reason': 'missing api key',
            'profiles': ['media_api'],
            'external_provider_egress': true,
            'operator_action': 'set OPENAI_API_KEY',
            'user_retryable': false,
          },
        },
        'modality_actions': {
          'audio': {
            'transcribe': {
              'enabled': false,
              'status': 'blocked',
              'reason': 'missing api key',
              'profiles': ['media_api'],
              'providers': ['openai_transcription'],
            },
          },
        },
        'degraded_components': [
          {
            'component_type': 'provider',
            'name': 'openai_transcription',
            'status': 'blocked',
            'reason': 'missing api key',
            'operator_action': 'set OPENAI_API_KEY',
            'user_retryable': false,
          },
        ],
        'provider_contract': {
          'openai_transcription': {'max_upload_bytes': 26214400},
        },
        'manifest_contract': {'artifact_payloads_bounded': true},
        'limits': {'max_bytes': 26214400},
      });

      expect(capabilities.enabled, true);
      expect(capabilities.defaultProfile, 'standard_local');
      expect(capabilities.profile('media_api')?.status, 'blocked');
      expect(capabilities.profile('media_api')?.inputModalities, [
        'audio',
        'video',
      ]);
      expect(
        capabilities.provider('openai_transcription')?.operatorAction,
        'set OPENAI_API_KEY',
      );
      expect(
        capabilities.modalityAction('audio', 'transcribe')?.providers,
        ['openai_transcription'],
      );
      expect(capabilities.degradedLabels, [
        'openai_transcription: set OPENAI_API_KEY',
      ]);
      expect(
        capabilities.providerContract['openai_transcription'],
        isA<Map<String, dynamic>>(),
      );
    });

    test('plans image upload from modality actions and degraded provider state',
        () {
      final capabilities = ExtractionCapabilities.fromMap({
        'enabled': true,
        'profiles_v2': const [],
        'modality_actions': {
          'image': {
            'metadata': {
              'enabled': true,
              'status': 'ok',
              'providers': ['image_metadata'],
              'artifact_types': ['image_regions', 'media_manifest'],
              'evidence_coordinates': ['bbox'],
              'memory_promotion': 'review_required',
              'source_text_policy': 'untrusted_evidence',
            },
            'vision': {
              'enabled': false,
              'status': 'blocked',
              'reason': 'provider_credential_missing',
              'operator_action': 'configure_provider_credential',
              'providers': ['openai_vision'],
              'artifact_types': ['vision_json'],
              'evidence_coordinates': ['bbox'],
              'external_provider_egress': true,
              'requires_explicit_external_ai': true,
              'fallback_profiles': ['standard_local'],
            },
          },
        },
        'limits': {'max_bytes': 1024},
      });

      final plan = capabilities.planAttachment(
        filename: 'alex-call.png',
        mime: 'image/png',
        bytes: 512,
      );

      expect(plan.modality, 'image');
      expect(plan.withinExtractionLimit, isTrue);
      expect(plan.compactLabel, 'Image: metadata, 1 degraded');
      expect(plan.enabledActions.map((action) => action.displayName), [
        'metadata',
      ]);
      expect(plan.degradedActions.single.displayName, 'vision');
      expect(plan.degradedActions.single.externalProviderEgress, isTrue);
      expect(plan.warnings, contains('vision: configure_provider_credential'));
    });

    test('plans unknown oversized file without faking extraction support', () {
      final capabilities = ExtractionCapabilities.fromMap({
        'enabled': true,
        'profiles_v2': const [],
        'modality_actions': const {},
        'limits': {'max_bytes': 3},
      });

      final plan = capabilities.planAttachment(
        filename: 'payload.bin',
        mime: 'application/octet-stream',
        bytes: 4,
      );

      expect(plan.modality, 'unknown');
      expect(plan.withinExtractionLimit, isFalse);
      expect(plan.actions, isEmpty);
      expect(plan.compactLabel, 'Extraction limit exceeded');
      expect(
        plan.warnings,
        contains(
            'Unknown file type; backend will store the file and inspect it safely'),
      );
    });
  });
}
