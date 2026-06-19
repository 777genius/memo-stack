import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

part 'marionette_e2e_runtime.dart';

Future<void> main() async {
  final config = MarionetteAnchorLifecycleConfig.fromEnv(Platform.environment);
  final runner = MarionetteAnchorLifecycleRunner(config);
  await runner.run();
}

class MarionetteAnchorLifecycleConfig {
  final String flutterBin;
  final String device;
  final String backendHost;
  final String backendPort;
  final String serviceToken;
  final String spaceSlug;
  final String scopeRef;
  final Uri? vmServiceUri;
  final bool keepAppRunning;
  final Duration startupTimeout;
  final Duration callTimeout;
  final String? flowReportOut;

  const MarionetteAnchorLifecycleConfig({
    required this.flutterBin,
    required this.device,
    required this.backendHost,
    required this.backendPort,
    required this.serviceToken,
    required this.spaceSlug,
    required this.scopeRef,
    required this.vmServiceUri,
    required this.keepAppRunning,
    required this.startupTimeout,
    required this.callTimeout,
    required this.flowReportOut,
  });

  factory MarionetteAnchorLifecycleConfig.fromEnv(
    Map<String, String> env,
  ) {
    final runId = env['INFINITY_CONTEXT_E2E_RUN_ID'] ??
        DateTime.now().millisecondsSinceEpoch.toString();
    final vmServiceValue = _env(env, 'INFINITY_CONTEXT_E2E_VM_SERVICE_URI');
    return MarionetteAnchorLifecycleConfig(
      flutterBin: _env(env, 'FLUTTER_BIN') ??
          _env(env, 'FLUTTER') ??
          _defaultFlutterBin(),
      device: _env(env, 'INFINITY_CONTEXT_E2E_DEVICE') ?? 'macos',
      backendHost: _env(env, 'INFINITY_CONTEXT_BACKEND_HOST') ?? '127.0.0.1',
      backendPort: _env(env, 'INFINITY_CONTEXT_BACKEND_PORT') ?? '7788',
      serviceToken:
          _env(env, 'INFINITY_CONTEXT_SERVICE_TOKEN') ?? 'local-dev-token',
      spaceSlug:
          _env(env, 'INFINITY_CONTEXT_SPACE_SLUG') ?? 'marionette-anchor-e2e',
      scopeRef: _env(env, 'INFINITY_CONTEXT_MEMORY_SCOPE_EXTERNAL_REF') ??
          'marionette-anchor-e2e-$runId',
      vmServiceUri:
          vmServiceValue == null ? null : _parseWebSocketUri(vmServiceValue),
      keepAppRunning: _truthy(env['INFINITY_CONTEXT_E2E_KEEP_APP_RUNNING']),
      startupTimeout: Duration(
        seconds:
            int.tryParse(env['INFINITY_CONTEXT_E2E_STARTUP_TIMEOUT'] ?? '') ??
                120,
      ),
      callTimeout: Duration(
        seconds:
            int.tryParse(env['INFINITY_CONTEXT_E2E_CALL_TIMEOUT'] ?? '') ?? 30,
      ),
      flowReportOut: _env(env, 'INFINITY_CONTEXT_E2E_FLOW_REPORT_OUT'),
    );
  }
}

List<_AttachmentCase> _attachmentCases(String runMarker) {
  return <_AttachmentCase>[
    _AttachmentCase(
      label: 'text',
      filename: 'attachment-text-$runMarker.txt',
      mime: 'text/plain',
      content: 'Attachment E2E $runMarker: Alex attached file evidence '
          'for Project Capture Target $runMarker.',
      text: 'Attachment text capture $runMarker should preserve file evidence.',
      expectedParserName: 'simple_text',
      expectedArtifactTypes: <String>{'markdown'},
    ),
    _AttachmentCase(
      label: 'image',
      filename: 'attachment-image-$runMarker.png',
      mime: 'image/png',
      contentBase64: _samplePngBase64(),
      text:
          'Attachment image capture $runMarker should preserve screenshot evidence.',
      expectedParserName: 'image_metadata',
      expectedArtifactTypes: <String>{'image_regions', 'markdown'},
    ),
    _AttachmentCase(
      label: 'audio',
      filename: 'attachment-audio-$runMarker.wav',
      mime: 'audio/wav',
      contentBase64: _sampleWavBase64(),
      text:
          'Attachment audio capture $runMarker should preserve media evidence.',
      expectedParserName: 'media_metadata',
      expectedArtifactTypes: <String>{'media_manifest', 'markdown'},
    ),
    _AttachmentCase(
      label: 'video',
      filename: 'attachment-video-$runMarker.mp4',
      mime: 'video/mp4',
      contentBase64: _sampleMp4Base64(),
      text:
          'Attachment video capture $runMarker should preserve keyframe evidence.',
      expectedParserName: 'media_metadata',
      expectedArtifactTypes: <String>{
        'keyframe',
        'media_manifest',
        'markdown',
        'video_frame_timeline',
      },
    ),
  ];
}

String _samplePngBase64() {
  return 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADUlEQVR42mP8'
      'z8BQDwAFgwJ/l5v2NwAAAABJRU5ErkJggg==';
}

String _sampleWavBase64() {
  return base64Encode(_sampleWavBytes());
}

List<int> _sampleWavBytes() {
  const sampleRate = 8000;
  const frameCount = 800;
  const channels = 1;
  const bytesPerSample = 2;
  const bitsPerSample = 16;
  const dataSize = frameCount * channels * bytesPerSample;
  final bytes = Uint8List(44 + dataSize);
  final data = ByteData.sublistView(bytes);
  _writeAscii(bytes, 0, 'RIFF');
  data.setUint32(4, 36 + dataSize, Endian.little);
  _writeAscii(bytes, 8, 'WAVE');
  _writeAscii(bytes, 12, 'fmt ');
  data.setUint32(16, 16, Endian.little);
  data.setUint16(20, 1, Endian.little);
  data.setUint16(22, channels, Endian.little);
  data.setUint32(24, sampleRate, Endian.little);
  data.setUint32(28, sampleRate * channels * bytesPerSample, Endian.little);
  data.setUint16(32, channels * bytesPerSample, Endian.little);
  data.setUint16(34, bitsPerSample, Endian.little);
  _writeAscii(bytes, 36, 'data');
  data.setUint32(40, dataSize, Endian.little);
  return bytes;
}

void _writeAscii(Uint8List bytes, int offset, String value) {
  for (var index = 0; index < value.length; index += 1) {
    bytes[offset + index] = value.codeUnitAt(index);
  }
}

String _sampleMp4Base64() {
  final tempDir = Directory.systemTemp.createTempSync(
    'infinity-context-video-fixture.',
  );
  try {
    final video = File('${tempDir.path}/fixture.mp4');
    final result = Process.runSync(
      'ffmpeg',
      <String>[
        '-y',
        '-v',
        'error',
        '-f',
        'lavfi',
        '-i',
        'color=c=black:s=32x32:d=1',
        '-pix_fmt',
        'yuv420p',
        video.path,
      ],
    );
    if (result.exitCode != 0 || !video.existsSync()) {
      throw StateError('failed to generate mp4 fixture: ${result.stderr}');
    }
    return base64Encode(video.readAsBytesSync());
  } finally {
    tempDir.deleteSync(recursive: true);
  }
}

class MarionetteFlowRecorder {
  final String? path;
  final String runMarker;
  final List<String> completedFlows = <String>[];

  MarionetteFlowRecorder({
    required this.path,
    required this.runMarker,
  });

  Future<void> markCompleted(String flow) async {
    if (!completedFlows.contains(flow)) {
      completedFlows.add(flow);
    }
    await write(status: 'running');
  }

  Future<void> write({required String status}) async {
    final output = path;
    if (output == null || output.isEmpty) return;
    final file = File(output);
    await file.parent.create(recursive: true);
    await file.writeAsString(
      '${jsonEncode({
            'schema_version': 1,
            'status': status,
            'run_marker': runMarker,
            'completed_flow_count': completedFlows.length,
            'completed_flows': completedFlows,
          })}\n',
    );
  }
}

class _AttachmentCase {
  final String label;
  final String filename;
  final String mime;
  final String text;
  final String expectedParserName;
  final Set<String> expectedArtifactTypes;
  final String? content;
  final String? contentBase64;

  const _AttachmentCase({
    required this.label,
    required this.filename,
    required this.mime,
    required this.text,
    required this.expectedParserName,
    required this.expectedArtifactTypes,
    this.content,
    this.contentBase64,
  });
}

class MarionetteAnchorLifecycleRunner {
  final MarionetteAnchorLifecycleConfig config;

  MarionetteAnchorLifecycleRunner(this.config);

  Future<void> run() async {
    final startedApp =
        config.vmServiceUri == null ? await _startFlutterApp(config) : null;
    final vmServiceUri = startedApp?.vmServiceUri ?? config.vmServiceUri!;
    VmServiceClient? client;
    InfinityContextExtensionClient? infinityContext;
    final runMarker = _runMarker(config.scopeRef);
    final flowRecorder = MarionetteFlowRecorder(
      path: config.flowReportOut,
      runMarker: runMarker,
    );
    var flowStatus = 'failed';

    try {
      _log('connecting to VM service at $vmServiceUri');
      client = await VmServiceClient.connect(vmServiceUri, config.callTimeout);
      infinityContext =
          InfinityContextExtensionClient(client, config.callTimeout);
      await infinityContext.init();

      final state = await infinityContext.waitUntilReady();
      _expect(
        state['connection'] == 'connected',
        'frontend did not report backend connection',
      );

      await infinityContext.call(
        'infinityContext.createMemoryScope',
        {
          'externalRef': config.scopeRef,
          'name': 'Marionette Anchor E2E $runMarker',
        },
      );

      await _runMemoryScopeManagementFlow(infinityContext, runMarker);
      await flowRecorder.markCompleted('memory_scope_management');
      await _runCaptureLinkingFlow(infinityContext, runMarker);
      await flowRecorder.markCompleted('capture_link_approve');
      await _runRejectedContextLinkFlow(infinityContext, runMarker);
      await flowRecorder.markCompleted('context_link_reject');
      await _runAttachmentCaptureFlow(infinityContext, runMarker);
      await flowRecorder.markCompleted('attachment_capture_extraction');
      await _runManualContextLinkFlow(infinityContext, runMarker);
      await flowRecorder.markCompleted('manual_context_link_override');
      final anchorBaselineState =
          await infinityContext.call('infinityContext.e2eState', {});
      final anchorBaseline =
          _int(anchorBaselineState['memoryBrowserAnchorCount']);
      final created = await infinityContext.call(
        'infinityContext.createMemoryAnchor',
        {
          'memoryScopeExternalRef': config.scopeRef,
          'kind': 'person',
          'label': 'Alex Script $runMarker',
          'aliases': 'Alex Script, AS-$runMarker',
          'description': 'Created by automated Marionette anchor lifecycle e2e',
        },
      );
      final targetAnchorId = _field(_map(created['anchor']), 'id');
      _expect(
        _int(created['memoryBrowserAnchorCount']) == anchorBaseline + 1,
        'create anchor did not add exactly one browser anchor',
      );
      _log('created anchor $targetAnchorId');

      final updated = await infinityContext.call(
        'infinityContext.updateMemoryAnchor',
        {
          'anchorId': targetAnchorId,
          'label': 'Alex Script $runMarker Updated',
          'aliases': 'Alex Script, AS-$runMarker, Alex Demo',
          'description': 'Updated by automated Marionette anchor lifecycle e2e',
        },
      );
      _expect(
        _field(_map(updated['anchor']), 'label').endsWith('Updated'),
        'update anchor did not return updated label',
      );

      final split = await infinityContext.call(
        'infinityContext.splitMemoryAnchorAlias',
        {
          'anchorId': targetAnchorId,
          'alias': 'AS-$runMarker',
          'newLabel': 'Alex Script Split $runMarker',
          'reason': 'automated Marionette anchor lifecycle e2e split',
        },
      );
      final splitAnchorId = _field(_map(split['splitAnchor']), 'id');
      _expect(
        _int(split['memoryBrowserAnchorCount']) == anchorBaseline + 2,
        'split alias did not produce the expected second anchor',
      );
      _log('split alias into anchor $splitAnchorId');

      final duplicate = await infinityContext.call(
        'infinityContext.createMemoryAnchor',
        {
          'memoryScopeExternalRef': config.scopeRef,
          'kind': 'person',
          'label': 'Alex Script $runMarker Candidate',
          'aliases': 'AS Candidate $runMarker, Alex Candidate $runMarker',
          'description': 'Possible duplicate for automated merge e2e',
        },
      );
      final duplicateAnchorId = _field(_map(duplicate['anchor']), 'id');
      _log('created duplicate candidate $duplicateAnchorId');

      var reviewState = duplicate;
      if (_int(reviewState['pendingAnchorMergeSuggestionCount']) == 0) {
        reviewState = await infinityContext.call(
          'infinityContext.backfillMemoryAnchors',
          {'limitPerSource': '25'},
        );
      }
      _expect(
        _int(reviewState['pendingAnchorMergeSuggestionCount']) > 0,
        'backend did not produce an anchor merge suggestion',
      );

      var merged = await infinityContext.call(
        'infinityContext.mergeFirstAnchorSuggestion',
        {
          'sourceAnchorId': duplicateAnchorId,
          'targetAnchorId': targetAnchorId,
        },
      );
      if (merged['merged'] != true) {
        merged = await infinityContext.call(
          'infinityContext.mergeFirstAnchorSuggestion',
          {
            'sourceAnchorId': targetAnchorId,
            'targetAnchorId': duplicateAnchorId,
          },
        );
      }
      _expect(merged['merged'] == true, 'merge suggestion was not applied');
      final mergedSourceAnchorId = _field(merged, 'mergedSourceAnchorId');
      final mergedTargetAnchorId = _field(merged, 'mergedTargetAnchorId');
      final anchorsAfterMerge =
          _list(merged['memoryBrowserAnchors']).map(_map).toList();
      _expect(
        anchorsAfterMerge
            .every((anchor) => _field(anchor, 'id') != mergedSourceAnchorId),
        'merged source anchor is still visible in memory browser',
      );
      _expect(
        anchorsAfterMerge
            .any((anchor) => _field(anchor, 'id') == mergedTargetAnchorId),
        'merged target anchor is not visible in memory browser',
      );
      _log(
        'merged $mergedSourceAnchorId into $mergedTargetAnchorId '
        'with ${merged['pendingAnchorMergeSuggestionCount']} suggestions left',
      );

      await _cleanupRunAnchors(infinityContext, runMarker);
      final cleanState =
          await infinityContext.call('infinityContext.e2eState', {});
      final remaining = _anchorsWithMarker(cleanState, runMarker);
      _expect(
        remaining.isEmpty,
        'cleanup left ${remaining.length} test anchors in memory browser',
      );
      await flowRecorder.markCompleted('anchor_lifecycle_cleanup');
      flowStatus = 'succeeded';

      _log('anchor lifecycle e2e passed');
    } finally {
      await flowRecorder.write(status: flowStatus);
      if (infinityContext != null) {
        await _bestEffortCleanup(infinityContext, runMarker);
      }
      await client?.close();
      if (startedApp != null && !config.keepAppRunning) {
        await startedApp.stop();
      }
    }
  }

  Future<void> _runMemoryScopeManagementFlow(
    InfinityContextExtensionClient infinityContext,
    String runMarker,
  ) async {
    final tempRef = 'marionette-scope-admin-$runMarker';
    final renamedRef = '$tempRef-renamed';
    final created = await infinityContext.call(
      'infinityContext.createMemoryScope',
      {
        'externalRef': tempRef,
        'name': 'Marionette Scope Admin $runMarker',
      },
    );
    final createdScopeId = _field(_map(created['memoryScope']), 'id');
    final updated = await infinityContext.call(
      'infinityContext.updateMemoryScope',
      {
        'memoryScopeId': createdScopeId,
        'externalRef': renamedRef,
        'name': 'Marionette Scope Admin Renamed $runMarker',
      },
    );
    _expect(
      _field(_map(updated['memoryScope']), 'externalRef') == renamedRef,
      'memory scope update did not return the renamed external ref',
    );
    final deleted = await infinityContext.call(
      'infinityContext.deleteMemoryScope',
      {'externalRef': renamedRef},
    );
    _expect(
      deleted['deletedMemoryScopeExternalRef'] == renamedRef,
      'memory scope delete did not delete the renamed scope',
    );
    final state = await infinityContext.call('infinityContext.e2eState', {});
    final refs = _list(state['memoryScopes'])
        .map(_map)
        .map((scope) => _field(scope, 'externalRef'))
        .toSet();
    _expect(!refs.contains(renamedRef), 'renamed test scope is still listed');
    await infinityContext.call(
      'infinityContext.switchMemoryScope',
      {'externalRef': config.scopeRef},
    );
    _log('created, renamed, and deleted temporary memory scope $renamedRef');
  }

  Future<void> _runCaptureLinkingFlow(
    InfinityContextExtensionClient infinityContext,
    String runMarker,
  ) async {
    final target = await infinityContext.call(
      'infinityContext.createMemoryAnchor',
      {
        'memoryScopeExternalRef': config.scopeRef,
        'kind': 'project',
        'label': 'Project Capture Target $runMarker',
        'aliases': 'Capture Target $runMarker, Project Link $runMarker',
        'description': 'Target anchor for automated capture linking e2e',
      },
    );
    final targetAnchorId = _field(_map(target['anchor']), 'id');
    _log('created capture link target $targetAnchorId');

    final captured = await infinityContext.call(
      'infinityContext.submitCapture',
      {
        'memoryScopeExternalRef': config.scopeRef,
        'threadTitle': 'Capture Link Thread $runMarker',
        'text': 'Alex confirmed Project Capture Target $runMarker should be '
            'linked to the onboarding screenshot note.',
      },
    );
    _expect(
      _int(captured['captureCount']) > 0,
      'submitCapture did not create a visible memory capture',
    );
    _expect(
      _field(_map(captured['latestCapture']), 'preview').contains(runMarker),
      'latest capture does not contain the run marker',
    );

    final pending = await _waitForPendingContextLinkSuggestion(
      infinityContext,
      targetAnchorId: targetAnchorId,
    );
    _expect(
      _int(pending['pendingLinkSuggestionCount']) > 0,
      'capture did not produce a pending context-link suggestion',
    );
    _log(
      'capture produced ${pending['pendingLinkSuggestionCount']} '
      'context-link suggestions',
    );

    final reviewed = await infinityContext.call(
      'infinityContext.reviewFirstPendingLinkSuggestion',
      {
        'approve': 'true',
        'targetId': targetAnchorId,
      },
    );
    _expect(
        reviewed['reviewed'] == true, 'no context-link suggestion reviewed');
    _expect(
      reviewed['reviewedTargetId'] == targetAnchorId,
      'reviewed suggestion target did not match the capture target anchor',
    );
    final linked = await _waitForContextLinkCount(infinityContext);
    _expect(
      _int(linked['memoryBrowserContextLinkCount']) > 0,
      'approved context-link suggestion did not create a visible link',
    );
    _log(
      'approved context-link suggestion ${reviewed['reviewedSuggestionId']} '
      'for capture flow',
    );
  }

  Future<void> _runAttachmentCaptureFlow(
    InfinityContextExtensionClient infinityContext,
    String runMarker,
  ) async {
    for (final attachment in _attachmentCases(runMarker)) {
      final params = <String, String>{
        'memoryScopeExternalRef': config.scopeRef,
        'threadTitle': 'Attachment ${attachment.label} Thread $runMarker',
        'filename': attachment.filename,
        'mime': attachment.mime,
        'text': attachment.text,
      };
      if (attachment.content != null) {
        params['content'] = attachment.content!;
      }
      if (attachment.contentBase64 != null) {
        params['contentBase64'] = attachment.contentBase64!;
      }
      final captured = await infinityContext.call(
        'infinityContext.submitAttachmentCapture',
        params,
      );
      final uploadedAssetIds =
          _list(captured['uploadedAssetIds']).map((item) => '$item').toList();
      _expect(
        uploadedAssetIds.length == 1,
        '${attachment.label} attachment did not return exactly one asset id',
      );
      final assetId = uploadedAssetIds.single;
      final latestCapture = _map(captured['latestCapture']);
      final captureAssetIds =
          _list(latestCapture['assetIds']).map((item) => '$item').toSet();
      _expect(
        captureAssetIds.contains(assetId),
        'latest ${attachment.label} capture does not reference asset $assetId',
      );

      final extraction = await _waitForAssetExtraction(
        infinityContext,
        assetId: assetId,
      );
      final parserName = _field(extraction, 'parserName');
      _expect(
        parserName == attachment.expectedParserName,
        '${attachment.label} attachment parser mismatch: $parserName',
      );
      _expect(
        _list(extraction['resultDocumentIds']).isNotEmpty,
        '${attachment.label} attachment extraction did not create a document',
      );
      final artifactTypes =
          _list(extraction['artifactTypes']).map((item) => '$item').toSet();
      for (final artifactType in attachment.expectedArtifactTypes) {
        _expect(
          artifactTypes.contains(artifactType),
          '${attachment.label} attachment missing artifact $artifactType',
        );
      }
      _log(
        'attachment ${attachment.label} linked asset $assetId '
        'with parser $parserName',
      );
    }
  }

  Future<void> _runRejectedContextLinkFlow(
    InfinityContextExtensionClient infinityContext,
    String runMarker,
  ) async {
    final baseline = await infinityContext.call('infinityContext.e2eState', {});
    final baselineLinkCount = _int(baseline['memoryBrowserContextLinkCount']);
    final target = await infinityContext.call(
      'infinityContext.createMemoryAnchor',
      {
        'memoryScopeExternalRef': config.scopeRef,
        'kind': 'project',
        'label': 'Rejected Link Target $runMarker',
        'aliases': 'Reject Target $runMarker',
        'description': 'Target anchor for rejected context-link e2e',
      },
    );
    final targetAnchorId = _field(_map(target['anchor']), 'id');
    _log('created rejected link target $targetAnchorId');

    await infinityContext.call(
      'infinityContext.submitCapture',
      {
        'memoryScopeExternalRef': config.scopeRef,
        'threadTitle': 'Rejected Link Thread $runMarker',
        'text': 'Alex mentioned Rejected Link Target $runMarker, but this '
            'automated run rejects the suggested relation.',
      },
    );
    await _waitForPendingContextLinkSuggestion(
      infinityContext,
      targetAnchorId: targetAnchorId,
    );

    final reviewed = await infinityContext.call(
      'infinityContext.reviewFirstPendingLinkSuggestion',
      {
        'approve': 'false',
        'targetId': targetAnchorId,
      },
    );
    _expect(
        reviewed['reviewed'] == true, 'no context-link suggestion rejected');
    _expect(
      reviewed['reviewAction'] == 'reject',
      'context-link suggestion was not rejected',
    );
    _expect(
      reviewed['reviewedTargetId'] == targetAnchorId,
      'rejected suggestion target did not match the requested anchor',
    );

    final rejectedState =
        await infinityContext.call('infinityContext.refresh', {});
    final remainingForTarget = _pendingSuggestionsForTarget(
      rejectedState,
      targetAnchorId,
    );
    _expect(
      remainingForTarget.isEmpty,
      'rejected target still has pending suggestions: $remainingForTarget',
    );
    _expect(
      _int(rejectedState['memoryBrowserContextLinkCount']) == baselineLinkCount,
      'rejected context-link suggestion created a visible link',
    );
    _log('rejected context-link suggestion for $targetAnchorId');
  }

  Future<void> _runManualContextLinkFlow(
    InfinityContextExtensionClient infinityContext,
    String runMarker,
  ) async {
    final baseline = await infinityContext.call('infinityContext.e2eState', {});
    final baselineLinkCount = _int(baseline['memoryBrowserContextLinkCount']);
    final target = await infinityContext.call(
      'infinityContext.createMemoryAnchor',
      {
        'memoryScopeExternalRef': config.scopeRef,
        'kind': 'project',
        'label': 'Manual Link Target $runMarker',
        'aliases': 'Manual Override Target $runMarker',
        'description': 'Target anchor for manual context-link e2e',
      },
    );
    final targetAnchorId = _field(_map(target['anchor']), 'id');
    _log('created manual link target $targetAnchorId');

    await infinityContext.call(
      'infinityContext.submitCapture',
      {
        'memoryScopeExternalRef': config.scopeRef,
        'threadTitle': 'Manual Link Thread $runMarker',
        'text': 'Alex confirmed Manual Link Target $runMarker should be '
            'linked with an edited manual relation.',
      },
    );
    await _waitForPendingContextLinkSuggestion(
      infinityContext,
      targetAnchorId: targetAnchorId,
    );

    final manual = await infinityContext.call(
      'infinityContext.createManualContextLinkFromSuggestion',
      {
        'suggestionTargetId': targetAnchorId,
        'targetType': 'anchor',
        'targetId': targetAnchorId,
        'relationType': 'supports',
        'confidence': 'medium',
        'reason': 'manual override from Marionette E2E',
      },
    );
    _expect(
      manual['manualLinked'] == true,
      'manual context link was not created from suggestion',
    );
    _expect(
      manual['manualLinkTargetId'] == targetAnchorId,
      'manual context link target did not match selected anchor',
    );

    await _waitForContextLinkCount(
      infinityContext,
      minimumCount: baselineLinkCount + 1,
    );
    _log('created manual context link for $targetAnchorId');
  }

  Future<Map<String, dynamic>> _waitForPendingContextLinkSuggestion(
    InfinityContextExtensionClient infinityContext, {
    required String targetAnchorId,
  }) async {
    final deadline = DateTime.now().add(config.callTimeout);
    Map<String, dynamic>? lastState;
    while (DateTime.now().isBefore(deadline)) {
      lastState = await infinityContext.call('infinityContext.refresh', {});
      final matching = _list(lastState['pendingLinkSuggestions'])
          .map(_map)
          .where((item) => _field(item, 'targetId') == targetAnchorId)
          .toList(growable: false);
      if (matching.isNotEmpty) {
        return lastState;
      }
      await Future<void>.delayed(const Duration(milliseconds: 400));
    }
    throw StateError(
      'No pending context-link suggestion before timeout: $lastState',
    );
  }

  List<Map<String, dynamic>> _pendingSuggestionsForTarget(
    Map<String, dynamic> state,
    String targetAnchorId,
  ) {
    return _list(state['pendingLinkSuggestions'])
        .map(_map)
        .where((item) => _field(item, 'targetId') == targetAnchorId)
        .toList(growable: false);
  }

  Future<Map<String, dynamic>> _waitForAssetExtraction(
    InfinityContextExtensionClient infinityContext, {
    required String assetId,
  }) async {
    final deadline = DateTime.now().add(
      Duration(seconds: config.callTimeout.inSeconds * 2),
    );
    Map<String, dynamic>? lastState;
    Map<String, dynamic>? lastJob;
    while (DateTime.now().isBefore(deadline)) {
      lastState = await infinityContext.call('infinityContext.refresh', {});
      for (final item in _list(lastState['assetExtractions'])) {
        final job = _map(item);
        if (_field(job, 'assetId') != assetId) continue;
        lastJob = job;
        final status = _field(job, 'status');
        if (status == 'succeeded') {
          return job;
        }
        if (status == 'failed' ||
            status == 'unsupported' ||
            status == 'canceled') {
          throw StateError(
            'Asset extraction reached terminal failure for $assetId: $job',
          );
        }
      }
      await Future<void>.delayed(const Duration(milliseconds: 500));
    }
    throw StateError(
      'No succeeded asset extraction before timeout for $assetId: '
      'lastJob=$lastJob lastState=$lastState',
    );
  }

  Future<Map<String, dynamic>> _waitForContextLinkCount(
    InfinityContextExtensionClient infinityContext, {
    int minimumCount = 1,
  }) async {
    final deadline = DateTime.now().add(config.callTimeout);
    Map<String, dynamic>? lastState;
    while (DateTime.now().isBefore(deadline)) {
      lastState = await infinityContext.call('infinityContext.refresh', {});
      if (_int(lastState['memoryBrowserContextLinkCount']) >= minimumCount) {
        return lastState;
      }
      await Future<void>.delayed(const Duration(milliseconds: 400));
    }
    throw StateError('No visible context link before timeout: $lastState');
  }

  Future<void> _cleanupRunAnchors(
    InfinityContextExtensionClient infinityContext,
    String runMarker,
  ) async {
    final state = await infinityContext.call('infinityContext.e2eState', {});
    final anchors = _anchorsWithMarker(state, runMarker);
    for (final anchor in anchors) {
      await infinityContext.call(
        'infinityContext.deleteMemoryAnchor',
        {
          'anchorId': _field(anchor, 'id'),
          'reason': 'automated Marionette anchor lifecycle e2e cleanup',
        },
      );
    }
  }

  Future<void> _bestEffortCleanup(
    InfinityContextExtensionClient infinityContext,
    String runMarker,
  ) async {
    try {
      await infinityContext.call(
        'infinityContext.switchMemoryScope',
        {'externalRef': config.scopeRef},
      );
      await _cleanupRunAnchors(infinityContext, runMarker);
      await infinityContext.call(
        'infinityContext.deleteMemoryScope',
        {'externalRef': config.scopeRef},
      );
      _log('deleted memory scope ${config.scopeRef}');
    } catch (error) {
      _log('cleanup warning: $error');
    }
  }
}
