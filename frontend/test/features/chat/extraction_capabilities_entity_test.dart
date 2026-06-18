import 'package:flutter_test/flutter_test.dart';
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
  });
}
