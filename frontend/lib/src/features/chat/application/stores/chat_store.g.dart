// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'chat_store.dart';

// **************************************************************************
// StoreGenerator
// **************************************************************************

// ignore_for_file: non_constant_identifier_names, unnecessary_brace_in_string_interps, unnecessary_lambdas, prefer_expression_function_bodies, lines_longer_than_80_chars, avoid_as, avoid_annotating_with_dynamic, no_leading_underscores_for_local_identifiers

mixin _$ChatStore on ChatStoreBase, Store {
  late final _$sessionsAtom =
      Atom(name: 'ChatStoreBase.sessions', context: context);

  @override
  ObservableList<ChatSession> get sessions {
    _$sessionsAtom.reportRead();
    return super.sessions;
  }

  @override
  set sessions(ObservableList<ChatSession> value) {
    _$sessionsAtom.reportWrite(value, super.sessions, () {
      super.sessions = value;
    });
  }

  late final _$activeChatIdAtom =
      Atom(name: 'ChatStoreBase.activeChatId', context: context);

  @override
  String get activeChatId {
    _$activeChatIdAtom.reportRead();
    return super.activeChatId;
  }

  @override
  set activeChatId(String value) {
    _$activeChatIdAtom.reportWrite(value, super.activeChatId, () {
      super.activeChatId = value;
    });
  }

  late final _$memoryScopesAtom =
      Atom(name: 'ChatStoreBase.memoryScopes', context: context);

  @override
  ObservableList<MemoryScope> get memoryScopes {
    _$memoryScopesAtom.reportRead();
    return super.memoryScopes;
  }

  @override
  set memoryScopes(ObservableList<MemoryScope> value) {
    _$memoryScopesAtom.reportWrite(value, super.memoryScopes, () {
      super.memoryScopes = value;
    });
  }

  late final _$activeMemoryScopeExternalRefAtom = Atom(
      name: 'ChatStoreBase.activeMemoryScopeExternalRef', context: context);

  @override
  String get activeMemoryScopeExternalRef {
    _$activeMemoryScopeExternalRefAtom.reportRead();
    return super.activeMemoryScopeExternalRef;
  }

  @override
  set activeMemoryScopeExternalRef(String value) {
    _$activeMemoryScopeExternalRefAtom
        .reportWrite(value, super.activeMemoryScopeExternalRef, () {
      super.activeMemoryScopeExternalRef = value;
    });
  }

  late final _$memoryScopesLoadingAtom =
      Atom(name: 'ChatStoreBase.memoryScopesLoading', context: context);

  @override
  bool get memoryScopesLoading {
    _$memoryScopesLoadingAtom.reportRead();
    return super.memoryScopesLoading;
  }

  @override
  set memoryScopesLoading(bool value) {
    _$memoryScopesLoadingAtom.reportWrite(value, super.memoryScopesLoading, () {
      super.memoryScopesLoading = value;
    });
  }

  late final _$memoryScopeErrorAtom =
      Atom(name: 'ChatStoreBase.memoryScopeError', context: context);

  @override
  String? get memoryScopeError {
    _$memoryScopeErrorAtom.reportRead();
    return super.memoryScopeError;
  }

  @override
  set memoryScopeError(String? value) {
    _$memoryScopeErrorAtom.reportWrite(value, super.memoryScopeError, () {
      super.memoryScopeError = value;
    });
  }

  late final _$assetExtractionsAtom =
      Atom(name: 'ChatStoreBase.assetExtractions', context: context);

  @override
  ObservableList<AssetExtractionJob> get assetExtractions {
    _$assetExtractionsAtom.reportRead();
    return super.assetExtractions;
  }

  @override
  set assetExtractions(ObservableList<AssetExtractionJob> value) {
    _$assetExtractionsAtom.reportWrite(value, super.assetExtractions, () {
      super.assetExtractions = value;
    });
  }

  late final _$assetExtractionsLoadingAtom =
      Atom(name: 'ChatStoreBase.assetExtractionsLoading', context: context);

  @override
  bool get assetExtractionsLoading {
    _$assetExtractionsLoadingAtom.reportRead();
    return super.assetExtractionsLoading;
  }

  @override
  set assetExtractionsLoading(bool value) {
    _$assetExtractionsLoadingAtom
        .reportWrite(value, super.assetExtractionsLoading, () {
      super.assetExtractionsLoading = value;
    });
  }

  late final _$assetExtractionErrorAtom =
      Atom(name: 'ChatStoreBase.assetExtractionError', context: context);

  @override
  String? get assetExtractionError {
    _$assetExtractionErrorAtom.reportRead();
    return super.assetExtractionError;
  }

  @override
  set assetExtractionError(String? value) {
    _$assetExtractionErrorAtom.reportWrite(value, super.assetExtractionError,
        () {
      super.assetExtractionError = value;
    });
  }

  late final _$memoryCapturesAtom =
      Atom(name: 'ChatStoreBase.memoryCaptures', context: context);

  @override
  ObservableList<MemoryCapture> get memoryCaptures {
    _$memoryCapturesAtom.reportRead();
    return super.memoryCaptures;
  }

  @override
  set memoryCaptures(ObservableList<MemoryCapture> value) {
    _$memoryCapturesAtom.reportWrite(value, super.memoryCaptures, () {
      super.memoryCaptures = value;
    });
  }

  late final _$memoryCapturesLoadingAtom =
      Atom(name: 'ChatStoreBase.memoryCapturesLoading', context: context);

  @override
  bool get memoryCapturesLoading {
    _$memoryCapturesLoadingAtom.reportRead();
    return super.memoryCapturesLoading;
  }

  @override
  set memoryCapturesLoading(bool value) {
    _$memoryCapturesLoadingAtom.reportWrite(value, super.memoryCapturesLoading,
        () {
      super.memoryCapturesLoading = value;
    });
  }

  late final _$memoryCaptureErrorAtom =
      Atom(name: 'ChatStoreBase.memoryCaptureError', context: context);

  @override
  String? get memoryCaptureError {
    _$memoryCaptureErrorAtom.reportRead();
    return super.memoryCaptureError;
  }

  @override
  set memoryCaptureError(String? value) {
    _$memoryCaptureErrorAtom.reportWrite(value, super.memoryCaptureError, () {
      super.memoryCaptureError = value;
    });
  }

  late final _$messagesAtom =
      Atom(name: 'ChatStoreBase.messages', context: context);

  @override
  ObservableList<ChatMessage> get messages {
    _$messagesAtom.reportRead();
    return super.messages;
  }

  @override
  set messages(ObservableList<ChatMessage> value) {
    _$messagesAtom.reportWrite(value, super.messages, () {
      super.messages = value;
    });
  }

  late final _$perChatUsdAtom =
      Atom(name: 'ChatStoreBase.perChatUsd', context: context);

  @override
  ObservableMap<String, double> get perChatUsd {
    _$perChatUsdAtom.reportRead();
    return super.perChatUsd;
  }

  @override
  set perChatUsd(ObservableMap<String, double> value) {
    _$perChatUsdAtom.reportWrite(value, super.perChatUsd, () {
      super.perChatUsd = value;
    });
  }

  late final _$perChatInTokensAtom =
      Atom(name: 'ChatStoreBase.perChatInTokens', context: context);

  @override
  ObservableMap<String, int> get perChatInTokens {
    _$perChatInTokensAtom.reportRead();
    return super.perChatInTokens;
  }

  @override
  set perChatInTokens(ObservableMap<String, int> value) {
    _$perChatInTokensAtom.reportWrite(value, super.perChatInTokens, () {
      super.perChatInTokens = value;
    });
  }

  late final _$perChatOutTokensAtom =
      Atom(name: 'ChatStoreBase.perChatOutTokens', context: context);

  @override
  ObservableMap<String, int> get perChatOutTokens {
    _$perChatOutTokensAtom.reportRead();
    return super.perChatOutTokens;
  }

  @override
  set perChatOutTokens(ObservableMap<String, int> value) {
    _$perChatOutTokensAtom.reportWrite(value, super.perChatOutTokens, () {
      super.perChatOutTokens = value;
    });
  }

  late final _$usageAtom = Atom(name: 'ChatStoreBase.usage', context: context);

  @override
  CostUsage? get usage {
    _$usageAtom.reportRead();
    return super.usage;
  }

  @override
  set usage(CostUsage? value) {
    _$usageAtom.reportWrite(value, super.usage, () {
      super.usage = value;
    });
  }

  late final _$totalUsdAtom =
      Atom(name: 'ChatStoreBase.totalUsd', context: context);

  @override
  double get totalUsd {
    _$totalUsdAtom.reportRead();
    return super.totalUsd;
  }

  @override
  set totalUsd(double value) {
    _$totalUsdAtom.reportWrite(value, super.totalUsd, () {
      super.totalUsd = value;
    });
  }

  late final _$totalInputTokensAtom =
      Atom(name: 'ChatStoreBase.totalInputTokens', context: context);

  @override
  int get totalInputTokens {
    _$totalInputTokensAtom.reportRead();
    return super.totalInputTokens;
  }

  @override
  set totalInputTokens(int value) {
    _$totalInputTokensAtom.reportWrite(value, super.totalInputTokens, () {
      super.totalInputTokens = value;
    });
  }

  late final _$totalOutputTokensAtom =
      Atom(name: 'ChatStoreBase.totalOutputTokens', context: context);

  @override
  int get totalOutputTokens {
    _$totalOutputTokensAtom.reportRead();
    return super.totalOutputTokens;
  }

  @override
  set totalOutputTokens(int value) {
    _$totalOutputTokensAtom.reportWrite(value, super.totalOutputTokens, () {
      super.totalOutputTokens = value;
    });
  }

  late final _$runningAtom =
      Atom(name: 'ChatStoreBase.running', context: context);

  @override
  bool get running {
    _$runningAtom.reportRead();
    return super.running;
  }

  @override
  set running(bool value) {
    _$runningAtom.reportWrite(value, super.running, () {
      super.running = value;
    });
  }

  late final _$connectionAtom =
      Atom(name: 'ChatStoreBase.connection', context: context);

  @override
  ConnectionStatus get connection {
    _$connectionAtom.reportRead();
    return super.connection;
  }

  @override
  set connection(ConnectionStatus value) {
    _$connectionAtom.reportWrite(value, super.connection, () {
      super.connection = value;
    });
  }

  late final _$connectionErrorAtom =
      Atom(name: 'ChatStoreBase.connectionError', context: context);

  @override
  String? get connectionError {
    _$connectionErrorAtom.reportRead();
    return super.connectionError;
  }

  @override
  set connectionError(String? value) {
    _$connectionErrorAtom.reportWrite(value, super.connectionError, () {
      super.connectionError = value;
    });
  }

  late final _$sendTaskAsyncAction =
      AsyncAction('ChatStoreBase.sendTask', context: context);

  @override
  Future<void> sendTask(String text) {
    return _$sendTaskAsyncAction.run(() => super.sendTask(text));
  }

  late final _$initAsyncAction =
      AsyncAction('ChatStoreBase.init', context: context);

  @override
  Future<void> init() {
    return _$initAsyncAction.run(() => super.init());
  }

  late final _$refreshMemoryScopesAsyncAction =
      AsyncAction('ChatStoreBase.refreshMemoryScopes', context: context);

  @override
  Future<void> refreshMemoryScopes() {
    return _$refreshMemoryScopesAsyncAction
        .run(() => super.refreshMemoryScopes());
  }

  late final _$refreshAssetExtractionsAsyncAction =
      AsyncAction('ChatStoreBase.refreshAssetExtractions', context: context);

  @override
  Future<void> refreshAssetExtractions({bool showLoading = true}) {
    return _$refreshAssetExtractionsAsyncAction
        .run(() => super.refreshAssetExtractions(showLoading: showLoading));
  }

  late final _$refreshMemoryCapturesAsyncAction =
      AsyncAction('ChatStoreBase.refreshMemoryCaptures', context: context);

  @override
  Future<void> refreshMemoryCaptures({bool showLoading = true}) {
    return _$refreshMemoryCapturesAsyncAction
        .run(() => super.refreshMemoryCaptures(showLoading: showLoading));
  }

  late final _$retryAssetExtractionAsyncAction =
      AsyncAction('ChatStoreBase.retryAssetExtraction', context: context);

  @override
  Future<void> retryAssetExtraction(AssetExtractionJob job) {
    return _$retryAssetExtractionAsyncAction
        .run(() => super.retryAssetExtraction(job));
  }

  late final _$createMemoryScopeAsyncAction =
      AsyncAction('ChatStoreBase.createMemoryScope', context: context);

  @override
  Future<MemoryScope?> createMemoryScope(
      {required String externalRef, required String name}) {
    return _$createMemoryScopeAsyncAction.run(
        () => super.createMemoryScope(externalRef: externalRef, name: name));
  }

  late final _$updateMemoryScopeAsyncAction =
      AsyncAction('ChatStoreBase.updateMemoryScope', context: context);

  @override
  Future<MemoryScope?> updateMemoryScope(MemoryScope scope,
      {required String externalRef, required String name}) {
    return _$updateMemoryScopeAsyncAction.run(() =>
        super.updateMemoryScope(scope, externalRef: externalRef, name: name));
  }

  late final _$deleteMemoryScopeAsyncAction =
      AsyncAction('ChatStoreBase.deleteMemoryScope', context: context);

  @override
  Future<void> deleteMemoryScope(MemoryScope scope) {
    return _$deleteMemoryScopeAsyncAction
        .run(() => super.deleteMemoryScope(scope));
  }

  late final _$setActiveMemoryScopeAsyncAction =
      AsyncAction('ChatStoreBase.setActiveMemoryScope', context: context);

  @override
  Future<void> setActiveMemoryScope(String externalRef) {
    return _$setActiveMemoryScopeAsyncAction
        .run(() => super.setActiveMemoryScope(externalRef));
  }

  late final _$setActiveChatAsyncAction =
      AsyncAction('ChatStoreBase.setActiveChat', context: context);

  @override
  Future<void> setActiveChat(String id) {
    return _$setActiveChatAsyncAction.run(() => super.setActiveChat(id));
  }

  late final _$ChatStoreBaseActionController =
      ActionController(name: 'ChatStoreBase', context: context);

  @override
  String createNewChat({String? title, String? memoryScopeExternalRef}) {
    final _$actionInfo = _$ChatStoreBaseActionController.startAction(
        name: 'ChatStoreBase.createNewChat');
    try {
      return super.createNewChat(
          title: title, memoryScopeExternalRef: memoryScopeExternalRef);
    } finally {
      _$ChatStoreBaseActionController.endAction(_$actionInfo);
    }
  }

  @override
  void renameChat(String id, String title) {
    final _$actionInfo = _$ChatStoreBaseActionController.startAction(
        name: 'ChatStoreBase.renameChat');
    try {
      return super.renameChat(id, title);
    } finally {
      _$ChatStoreBaseActionController.endAction(_$actionInfo);
    }
  }

  @override
  void removeChat(String id) {
    final _$actionInfo = _$ChatStoreBaseActionController.startAction(
        name: 'ChatStoreBase.removeChat');
    try {
      return super.removeChat(id);
    } finally {
      _$ChatStoreBaseActionController.endAction(_$actionInfo);
    }
  }

  @override
  String toString() {
    return '''
sessions: ${sessions},
activeChatId: ${activeChatId},
memoryScopes: ${memoryScopes},
activeMemoryScopeExternalRef: ${activeMemoryScopeExternalRef},
memoryScopesLoading: ${memoryScopesLoading},
memoryScopeError: ${memoryScopeError},
assetExtractions: ${assetExtractions},
assetExtractionsLoading: ${assetExtractionsLoading},
assetExtractionError: ${assetExtractionError},
memoryCaptures: ${memoryCaptures},
memoryCapturesLoading: ${memoryCapturesLoading},
memoryCaptureError: ${memoryCaptureError},
messages: ${messages},
perChatUsd: ${perChatUsd},
perChatInTokens: ${perChatInTokens},
perChatOutTokens: ${perChatOutTokens},
usage: ${usage},
totalUsd: ${totalUsd},
totalInputTokens: ${totalInputTokens},
totalOutputTokens: ${totalOutputTokens},
running: ${running},
connection: ${connection},
connectionError: ${connectionError}
    ''';
  }
}
