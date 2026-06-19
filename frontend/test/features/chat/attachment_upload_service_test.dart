import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/src/features/chat/application/services/attachment_upload_models.dart';
import 'package:frontend/src/features/chat/application/services/attachment_upload_service.dart';
import 'package:frontend/src/features/chat/domain/entities/asset_extraction.dart';
import 'package:frontend/src/features/chat/domain/entities/chat_message.dart';
import 'package:frontend/src/features/chat/domain/entities/extraction_capabilities.dart';
import 'package:frontend/src/features/chat/domain/repositories/attachment_upload_limits.dart';
import 'package:frontend/src/features/chat/domain/repositories/chat_repository.dart';
import 'package:frontend/src/features/chat/domain/repositories/extraction_capability_provider.dart';

void main() {
  group('AttachmentUploadDraft', () {
    test('detects image files by MIME when filename has no extension', () {
      final draft = AttachmentUploadDraft.file(
        name: 'clipboard-upload',
        bytes: [1, 2, 3],
        mime: 'image/png',
      );

      expect(draft.isImage, isTrue);
    });
  });

  group('AttachmentUploadService', () {
    test('rejects files above backend upload limit before network', () async {
      final repo = _RecordingUploadRepository();
      final limits = _StaticUploadLimits(3);
      final progress = _RecordingUploadProgress();
      final service = AttachmentUploadService(repo: repo, limits: limits);

      final uploaded = await service.uploadAll(
        [
          AttachmentUploadDraft.file(
            name: 'clip.mp4',
            bytes: [1, 2, 3, 4],
            mime: 'video/mp4',
          ),
        ],
        progress: progress,
      );

      expect(uploaded, isEmpty);
      expect(repo.uploadedNames, isEmpty);
      expect(limits.calls, 1);
      expect(progress.started, ['clip.mp4']);
      expect(
        progress.failures.single,
        'clip.mp4: File is too large: 4 B exceeds 3 B upload limit',
      );
    });

    test('uses fallback upload limit when capabilities are unavailable',
        () async {
      final repo = _RecordingUploadRepository();
      final limits = _FailingUploadLimits();
      final progress = _RecordingUploadProgress();
      final service = AttachmentUploadService(
        repo: repo,
        limits: limits,
        maxBytes: 4,
      );

      final uploaded = await service.uploadAll(
        [
          AttachmentUploadDraft.file(
            name: 'note.txt',
            bytes: [1, 2, 3],
            mime: 'text/plain',
          ),
        ],
        progress: progress,
      );

      expect(uploaded, ['file-1']);
      expect(repo.uploadedNames, ['note.txt']);
      expect(limits.calls, 1);
      expect(progress.completed, ['note.txt']);
      expect(progress.failures, isEmpty);
    });

    test('uses accepted file count for mixed batch metadata', () async {
      final repo = _RecordingUploadRepository();
      final limits = _StaticUploadLimits(3);
      final progress = _RecordingUploadProgress();
      final service = AttachmentUploadService(repo: repo, limits: limits);

      final uploaded = await service.uploadAll(
        [
          AttachmentUploadDraft.file(
            name: 'first.txt',
            bytes: [1, 2],
            mime: 'text/plain',
          ),
          AttachmentUploadDraft.file(
            name: 'too-large.txt',
            bytes: [1, 2, 3, 4],
            mime: 'text/plain',
          ),
          AttachmentUploadDraft.file(
            name: 'second.txt',
            bytes: [3],
            mime: 'text/plain',
          ),
        ],
        progress: progress,
      );

      expect(uploaded, ['file-1', 'file-2']);
      expect(repo.uploadedNames, ['first.txt', 'second.txt']);
      expect(repo.batchSizes, [2, 2]);
      expect(repo.batchIndexes, [1, 2]);
      expect(repo.batchIds.toSet(), hasLength(1));
      expect(progress.failures.single, startsWith('too-large.txt:'));
      expect(progress.completed, ['first.txt', 'second.txt']);
    });

    test('emits capability-derived analysis label for upload progress',
        () async {
      final repo = _RecordingUploadRepository();
      final progress = _RecordingUploadProgress();
      final service = AttachmentUploadService(
        repo: repo,
        capabilityProvider: _StaticExtractionCapabilityProvider(
          ExtractionCapabilities.fromMap({
            'enabled': true,
            'profiles_v2': const [],
            'modality_actions': {
              'image': {
                'metadata': {
                  'enabled': true,
                  'status': 'ok',
                  'artifact_types': ['image_regions'],
                  'evidence_coordinates': ['bbox'],
                },
                'vision': {
                  'enabled': false,
                  'status': 'blocked',
                  'reason': 'provider_credential_missing',
                  'operator_action': 'configure_provider_credential',
                  'artifact_types': ['vision_json'],
                  'evidence_coordinates': ['bbox'],
                  'external_provider_egress': true,
                  'requires_explicit_external_ai': true,
                },
              },
            },
            'limits': {'max_bytes': 1024},
          }),
        ),
      );

      final uploaded = await service.uploadAll(
        [
          AttachmentUploadDraft.file(
            name: 'screen.png',
            bytes: [1, 2, 3],
            mime: 'image/png',
          ),
        ],
        progress: progress,
      );

      expect(uploaded, ['file-1']);
      expect(progress.analysisLabels, ['Image: metadata, 1 degraded']);
      expect(progress.analysisDegraded, [true]);
    });
  });
}

class _StaticUploadLimits implements AttachmentUploadLimits {
  final int value;
  var calls = 0;

  _StaticUploadLimits(this.value);

  @override
  Future<int> maxUploadBytes() async {
    calls += 1;
    return value;
  }
}

class _FailingUploadLimits implements AttachmentUploadLimits {
  var calls = 0;

  @override
  Future<int> maxUploadBytes() async {
    calls += 1;
    throw StateError('capabilities unavailable');
  }
}

class _RecordingUploadProgress implements AttachmentUploadProgress {
  final started = <String>[];
  final failures = <String>[];
  final completed = <String>[];

  @override
  void start(
    String name,
    int total, {
    void Function()? onCancel,
    List<int>? previewBytes,
    String? analysisLabel,
    bool analysisDegraded = false,
  }) {
    started.add(name);
    analysisLabels.add(analysisLabel);
    this.analysisDegraded.add(analysisDegraded);
  }

  @override
  void progress(String name, int sent, int total) {}

  @override
  void fail(String name, String message) {
    failures.add('$name: $message');
  }

  @override
  void complete(String name) {
    completed.add(name);
  }

  final analysisLabels = <String?>[];
  final analysisDegraded = <bool>[];
}

class _StaticExtractionCapabilityProvider
    implements ExtractionCapabilityProvider {
  final ExtractionCapabilities capabilities;

  const _StaticExtractionCapabilityProvider(this.capabilities);

  @override
  Future<ExtractionCapabilities> getExtractionCapabilities() async {
    return capabilities;
  }
}

class _RecordingUploadRepository implements ChatRepository {
  final uploadedNames = <String>[];
  final batchIds = <String?>[];
  final batchSizes = <int?>[];
  final batchIndexes = <int?>[];
  var _seq = 0;

  @override
  Future<String> uploadFile(
    String name,
    List<int> bytes, {
    String? mime,
    void Function(int sent, int total)? onProgress,
    void Function(void Function())? onCreateCancel,
    String? previewBase64,
    String? batchId,
    int? batchSize,
    int? batchIndex,
  }) async {
    uploadedNames.add(name);
    batchIds.add(batchId);
    batchSizes.add(batchSize);
    batchIndexes.add(batchIndex);
    onProgress?.call(bytes.length, bytes.length);
    return 'file-${++_seq}';
  }

  @override
  Stream<ChatMessage> messages() => const Stream<ChatMessage>.empty();

  @override
  Future<List<AssetExtractionJob>> listAssetExtractions({
    String? status,
    int limit = 50,
  }) async {
    return const <AssetExtractionJob>[];
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}
