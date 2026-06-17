import 'dart:async';
import 'dart:convert';
import 'dart:io';

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
  });

  factory MarionetteAnchorLifecycleConfig.fromEnv(
    Map<String, String> env,
  ) {
    final runId = env['MEMO_STACK_E2E_RUN_ID'] ??
        DateTime.now().millisecondsSinceEpoch.toString();
    final vmServiceValue = _env(env, 'MEMO_STACK_E2E_VM_SERVICE_URI');
    return MarionetteAnchorLifecycleConfig(
      flutterBin: _env(env, 'FLUTTER_BIN') ??
          _env(env, 'FLUTTER') ??
          _defaultFlutterBin(),
      device: _env(env, 'MEMO_STACK_E2E_DEVICE') ?? 'macos',
      backendHost: _env(env, 'MEMO_STACK_BACKEND_HOST') ?? '127.0.0.1',
      backendPort: _env(env, 'MEMO_STACK_BACKEND_PORT') ?? '7788',
      serviceToken: _env(env, 'MEMO_STACK_SERVICE_TOKEN') ?? 'local-dev-token',
      spaceSlug: _env(env, 'MEMO_STACK_SPACE_SLUG') ?? 'marionette-anchor-e2e',
      scopeRef: _env(env, 'MEMO_STACK_MEMORY_SCOPE_EXTERNAL_REF') ??
          'marionette-anchor-e2e-$runId',
      vmServiceUri:
          vmServiceValue == null ? null : _parseWebSocketUri(vmServiceValue),
      keepAppRunning: _truthy(env['MEMO_STACK_E2E_KEEP_APP_RUNNING']),
      startupTimeout: Duration(
        seconds:
            int.tryParse(env['MEMO_STACK_E2E_STARTUP_TIMEOUT'] ?? '') ?? 120,
      ),
      callTimeout: Duration(
        seconds: int.tryParse(env['MEMO_STACK_E2E_CALL_TIMEOUT'] ?? '') ?? 30,
      ),
    );
  }
}

class MarionetteAnchorLifecycleRunner {
  final MarionetteAnchorLifecycleConfig config;

  MarionetteAnchorLifecycleRunner(this.config);

  Future<void> run() async {
    final startedApp =
        config.vmServiceUri == null ? await _startFlutterApp(config) : null;
    final vmServiceUri = startedApp?.vmServiceUri ?? config.vmServiceUri!;
    VmServiceClient? client;
    MemoStackExtensionClient? memoStack;
    final runMarker = _runMarker(config.scopeRef);

    try {
      _log('connecting to VM service at $vmServiceUri');
      client = await VmServiceClient.connect(vmServiceUri, config.callTimeout);
      memoStack = MemoStackExtensionClient(client, config.callTimeout);
      await memoStack.init();

      final state = await memoStack.waitUntilReady();
      _expect(
        state['connection'] == 'connected',
        'frontend did not report backend connection',
      );

      await memoStack.call(
        'memoStack.createMemoryScope',
        {
          'externalRef': config.scopeRef,
          'name': 'Marionette Anchor E2E $runMarker',
        },
      );

      await _runCaptureLinkingFlow(memoStack, runMarker);
      await _runAttachmentCaptureFlow(memoStack, runMarker);
      await _runManualContextLinkFlow(memoStack, runMarker);
      final anchorBaselineState =
          await memoStack.call('memoStack.e2eState', {});
      final anchorBaseline =
          _int(anchorBaselineState['memoryBrowserAnchorCount']);
      final created = await memoStack.call(
        'memoStack.createMemoryAnchor',
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

      final updated = await memoStack.call(
        'memoStack.updateMemoryAnchor',
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

      final split = await memoStack.call(
        'memoStack.splitMemoryAnchorAlias',
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

      final duplicate = await memoStack.call(
        'memoStack.createMemoryAnchor',
        {
          'memoryScopeExternalRef': config.scopeRef,
          'kind': 'person',
          'label': 'Alex Script Demo $runMarker',
          'aliases': 'Alex Demo, Alex Script',
          'description': 'Possible duplicate for automated merge e2e',
        },
      );
      final duplicateAnchorId = _field(_map(duplicate['anchor']), 'id');
      _log('created duplicate candidate $duplicateAnchorId');

      var reviewState = duplicate;
      if (_int(reviewState['pendingAnchorMergeSuggestionCount']) == 0) {
        reviewState = await memoStack.call(
          'memoStack.backfillMemoryAnchors',
          {'limitPerSource': '25'},
        );
      }
      _expect(
        _int(reviewState['pendingAnchorMergeSuggestionCount']) > 0,
        'backend did not produce an anchor merge suggestion',
      );

      var merged = await memoStack.call(
        'memoStack.mergeFirstAnchorSuggestion',
        {
          'sourceAnchorId': duplicateAnchorId,
          'targetAnchorId': targetAnchorId,
        },
      );
      if (merged['merged'] != true) {
        merged = await memoStack.call(
          'memoStack.mergeFirstAnchorSuggestion',
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

      await _cleanupRunAnchors(memoStack, runMarker);
      final cleanState = await memoStack.call('memoStack.e2eState', {});
      final remaining = _anchorsWithMarker(cleanState, runMarker);
      _expect(
        remaining.isEmpty,
        'cleanup left ${remaining.length} test anchors in memory browser',
      );

      _log('anchor lifecycle e2e passed');
    } finally {
      if (memoStack != null) {
        await _bestEffortCleanup(memoStack, runMarker);
      }
      await client?.close();
      if (startedApp != null && !config.keepAppRunning) {
        await startedApp.stop();
      }
    }
  }

  Future<void> _runCaptureLinkingFlow(
    MemoStackExtensionClient memoStack,
    String runMarker,
  ) async {
    final target = await memoStack.call(
      'memoStack.createMemoryAnchor',
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

    final captured = await memoStack.call(
      'memoStack.submitCapture',
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
      memoStack,
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

    final reviewed = await memoStack.call(
      'memoStack.reviewFirstPendingLinkSuggestion',
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
    final linked = await _waitForContextLinkCount(memoStack);
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
    MemoStackExtensionClient memoStack,
    String runMarker,
  ) async {
    final captured = await memoStack.call(
      'memoStack.submitAttachmentCapture',
      {
        'memoryScopeExternalRef': config.scopeRef,
        'threadTitle': 'Attachment Capture Thread $runMarker',
        'filename': 'attachment-$runMarker.txt',
        'mime': 'text/plain',
        'content': 'Attachment E2E $runMarker: Alex attached file evidence '
            'for Project Capture Target $runMarker.',
        'text': 'Attachment capture $runMarker should preserve file evidence.',
      },
    );
    final uploadedAssetIds =
        _list(captured['uploadedAssetIds']).map((item) => '$item').toList();
    _expect(
      uploadedAssetIds.length == 1,
      'submitAttachmentCapture did not return exactly one uploaded asset id',
    );
    final assetId = uploadedAssetIds.single;
    final latestCapture = _map(captured['latestCapture']);
    final captureAssetIds =
        _list(latestCapture['assetIds']).map((item) => '$item').toSet();
    _expect(
      captureAssetIds.contains(assetId),
      'latest capture does not reference uploaded asset $assetId',
    );

    final extraction = await _waitForAssetExtraction(
      memoStack,
      assetId: assetId,
    );
    _expect(
      _field(extraction, 'parserName') == 'simple_text',
      'text attachment was not parsed by simple_text',
    );
    _expect(
      _list(extraction['resultDocumentIds']).isNotEmpty,
      'text attachment extraction did not create a document',
    );
    _expect(
      _list(extraction['artifactTypes']).contains('markdown'),
      'text attachment extraction did not create a markdown artifact',
    );
    _log('attachment capture linked asset $assetId to extracted document');
  }

  Future<void> _runManualContextLinkFlow(
    MemoStackExtensionClient memoStack,
    String runMarker,
  ) async {
    final baseline = await memoStack.call('memoStack.e2eState', {});
    final baselineLinkCount = _int(baseline['memoryBrowserContextLinkCount']);
    final target = await memoStack.call(
      'memoStack.createMemoryAnchor',
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

    await memoStack.call(
      'memoStack.submitCapture',
      {
        'memoryScopeExternalRef': config.scopeRef,
        'threadTitle': 'Manual Link Thread $runMarker',
        'text': 'Alex confirmed Manual Link Target $runMarker should be '
            'linked with an edited manual relation.',
      },
    );
    await _waitForPendingContextLinkSuggestion(
      memoStack,
      targetAnchorId: targetAnchorId,
    );

    final manual = await memoStack.call(
      'memoStack.createManualContextLinkFromSuggestion',
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
      memoStack,
      minimumCount: baselineLinkCount + 1,
    );
    _log('created manual context link for $targetAnchorId');
  }

  Future<Map<String, dynamic>> _waitForPendingContextLinkSuggestion(
    MemoStackExtensionClient memoStack, {
    required String targetAnchorId,
  }) async {
    final deadline = DateTime.now().add(config.callTimeout);
    Map<String, dynamic>? lastState;
    while (DateTime.now().isBefore(deadline)) {
      lastState = await memoStack.call('memoStack.refresh', {});
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

  Future<Map<String, dynamic>> _waitForAssetExtraction(
    MemoStackExtensionClient memoStack, {
    required String assetId,
  }) async {
    final deadline = DateTime.now().add(
      Duration(seconds: config.callTimeout.inSeconds * 2),
    );
    Map<String, dynamic>? lastState;
    Map<String, dynamic>? lastJob;
    while (DateTime.now().isBefore(deadline)) {
      lastState = await memoStack.call('memoStack.refresh', {});
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
    MemoStackExtensionClient memoStack, {
    int minimumCount = 1,
  }) async {
    final deadline = DateTime.now().add(config.callTimeout);
    Map<String, dynamic>? lastState;
    while (DateTime.now().isBefore(deadline)) {
      lastState = await memoStack.call('memoStack.refresh', {});
      if (_int(lastState['memoryBrowserContextLinkCount']) >= minimumCount) {
        return lastState;
      }
      await Future<void>.delayed(const Duration(milliseconds: 400));
    }
    throw StateError('No visible context link before timeout: $lastState');
  }

  Future<void> _cleanupRunAnchors(
    MemoStackExtensionClient memoStack,
    String runMarker,
  ) async {
    final state = await memoStack.call('memoStack.e2eState', {});
    final anchors = _anchorsWithMarker(state, runMarker);
    for (final anchor in anchors) {
      await memoStack.call(
        'memoStack.deleteMemoryAnchor',
        {
          'anchorId': _field(anchor, 'id'),
          'reason': 'automated Marionette anchor lifecycle e2e cleanup',
        },
      );
    }
  }

  Future<void> _bestEffortCleanup(
    MemoStackExtensionClient memoStack,
    String runMarker,
  ) async {
    try {
      await memoStack.call(
        'memoStack.switchMemoryScope',
        {'externalRef': config.scopeRef},
      );
      await _cleanupRunAnchors(memoStack, runMarker);
      await memoStack.call(
        'memoStack.deleteMemoryScope',
        {'externalRef': config.scopeRef},
      );
      _log('deleted memory scope ${config.scopeRef}');
    } catch (error) {
      _log('cleanup warning: $error');
    }
  }
}
