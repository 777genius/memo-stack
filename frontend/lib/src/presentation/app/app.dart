import 'dart:async';

import 'package:flutter/foundation.dart' show kDebugMode;
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:frontend/src/app/debug/marionette_e2e_extensions.dart';
import 'package:frontend/src/features/chat/application/services/attachment_upload_models.dart';
import 'package:frontend/src/features/chat/application/services/attachment_upload_service.dart';
import 'package:frontend/src/features/chat/application/services/open_chat_attachment.dart';
import 'package:frontend/src/features/chat/application/services/open_extraction_artifact.dart';
import 'package:frontend/src/features/chat/application/stores/chat_store.dart';
import 'package:frontend/src/features/chat/data/repositories/chat_repository_impl.dart';
import 'package:frontend/src/features/chat/application/services/downloaded_file_opener.dart';
import 'package:frontend/src/features/chat/domain/repositories/chat_repository.dart';
import 'package:frontend/src/features/chat/data/datasources/backend_rest_client.dart';
import 'package:frontend/src/features/chat/data/services/local_downloaded_file_opener.dart';
import 'package:frontend/src/features/chat/data/services/pasteboard_clipboard_attachment_reader.dart';
import 'package:frontend/src/features/chat/data/services/platform_attachment_file_picker.dart';
import 'package:frontend/src/features/chat/domain/repositories/attachment_upload_limits.dart';
import 'package:frontend/src/app/config/app_config.dart';
import 'package:frontend/src/presentation/stores/theme_store.dart';
import 'package:frontend/src/presentation/theme/app_theme.dart';
import 'package:frontend/src/presentation/app/app_shell.dart';
import 'package:frontend/src/features/chat/application/ports/chat_cache.dart';
import 'package:frontend/src/features/chat/data/cache/hive_chat_cache.dart';

class AppRoot extends StatelessWidget {
  const AppRoot({super.key});

  @override
  Widget build(BuildContext context) {
    final themeStore = context.watch<ThemeStore>();
    final light = ThemeData(
      useMaterial3: true,
      colorSchemeSeed: Colors.blue,
      scaffoldBackgroundColor: Colors.transparent,
      canvasColor: Colors.transparent,
      extensions: [
        const AppThemeColors(
          userBubbleBg: Color(0xFF1565C0),
          userBubbleFg: Colors.white,
          assistantBubbleBg: Color(0xFFF3F4F6),
          assistantBubbleFg: Color(0xFF111827),
          surfaceBorder: Color(0xFFE5E7EB),
          usageBorder: Color(0xFFFFB74D),
          usageFill: Color(0xFFFFF3E0),
          actionTealBorder: Color(0xFF26A69A),
          actionTealFill: Color(0xFFE0F2F1),
          actionIndigoBorder: Color(0xFF5C6BC0),
          actionIndigoFill: Color(0xFFE8EAF6),
          actionPurpleBorder: Color(0xFF9575CD),
          actionPurpleFill: Color(0xFFF3E5F5),
          actionBlueGreyBorder: Color(0xFF78909C),
          actionBlueGreyFill: Color(0xFFECEFF1),
          actionGreenBorder: Color(0xFF66BB6A),
          actionGreenFill: Color(0xFFE8F5E9),
          actionOrangeBorder: Color(0xFFFFA726),
          actionOrangeFill: Color(0xFFFFF3E0),
        ),
        const AppThemeStyles(
          body: TextStyle(fontSize: 14, height: 1.35),
          bodySmall: TextStyle(fontSize: 12, height: 1.30),
          caption: TextStyle(fontSize: 11, height: 1.25),
          labelSmall: TextStyle(
              fontSize: 10, height: 1.20, fontWeight: FontWeight.w600),
        ),
      ],
    );
    final dark = ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorSchemeSeed: Colors.blue,
      scaffoldBackgroundColor: Colors.transparent,
      canvasColor: Colors.transparent,
      extensions: [
        const AppThemeColors(
          userBubbleBg: Color(0xFF1E3A8A),
          userBubbleFg: Colors.white,
          assistantBubbleBg: Color(0xFF111827),
          assistantBubbleFg: Color(0xFFE5E7EB),
          surfaceBorder: Color(0xFF374151),
          usageBorder: Color(0xFFFFB74D),
          usageFill: Color(0xFF3B2F1A),
          actionTealBorder: Color(0xFF26A69A),
          actionTealFill: Color(0xFF0B2F2C),
          actionIndigoBorder: Color(0xFF5C6BC0),
          actionIndigoFill: Color(0xFF22253E),
          actionPurpleBorder: Color(0xFF9575CD),
          actionPurpleFill: Color(0xFF2B2140),
          actionBlueGreyBorder: Color(0xFF90A4AE),
          actionBlueGreyFill: Color(0xFF1F2A30),
          actionGreenBorder: Color(0xFF66BB6A),
          actionGreenFill: Color(0xFF1E2A1F),
          actionOrangeBorder: Color(0xFFFFA726),
          actionOrangeFill: Color(0xFF3B2F1A),
        ),
        const AppThemeStyles(
          body: TextStyle(fontSize: 14, height: 1.35),
          bodySmall: TextStyle(fontSize: 12, height: 1.30),
          caption: TextStyle(fontSize: 11, height: 1.25),
          labelSmall: TextStyle(
              fontSize: 10, height: 1.20, fontWeight: FontWeight.w600),
        ),
      ],
    );

    return MaterialApp(
      title: 'Memo Stack',
      theme: light,
      darkTheme: dark,
      themeMode: themeStore.mode,
      builder: (context, child) {
        final appChild = child ?? const SizedBox.shrink();
        return MultiProvider(
          providers: [
            Provider(create: (_) => BackendRestClient()),
            Provider<DownloadedFileOpener>(
              create: (_) => LocalDownloadedFileOpener(),
            ),
            Provider<AttachmentFilePicker>(
              create: (_) => const PlatformAttachmentFilePicker(),
            ),
            Provider<ClipboardAttachmentReader>(
              create: (_) => const PasteboardClipboardAttachmentReader(),
            ),
            Provider<ChatCache>(create: (_) => HiveChatCache()),
            ProxyProvider2<AppConfig, BackendRestClient, ChatRepository>(
              update: (_, cfg, rest, prev) {
                rest.baseUrl = cfg.restBase();
                rest.bearer = cfg.token;
                final repo = prev ?? ChatRepositoryImpl(rest);
                if (repo is ChatRepositoryImpl) {
                  repo.updateScopeGetters(
                    spaceSlug: () => cfg.spaceSlug,
                    memoryScopeExternalRef: () => cfg.memoryScopeExternalRef,
                  );
                }
                return repo;
              },
              dispose: (_, repo) {
                if (repo is ChatRepositoryImpl) {
                  unawaited(repo.dispose());
                }
              },
            ),
            ProxyProvider<ChatRepository, AttachmentUploadService>(
              update: (_, repo, __) => AttachmentUploadService(
                repo: repo,
                limits: repo is AttachmentUploadLimits
                    ? repo as AttachmentUploadLimits
                    : null,
              ),
            ),
            ProxyProvider2<ChatRepository, DownloadedFileOpener,
                OpenExtractionArtifact>(
              update: (_, repo, opener, __) => OpenExtractionArtifact(
                repo: repo,
                opener: opener,
              ),
            ),
            ProxyProvider2<ChatRepository, DownloadedFileOpener,
                OpenChatAttachment>(
              update: (_, repo, opener, __) => OpenChatAttachment(
                repo: repo,
                opener: opener,
              ),
            ),
            ProxyProvider2<ChatRepository, ChatCache, ChatStore>(
              update: (_, repo, cache, prev) => prev ?? ChatStore(repo, cache),
              dispose: (_, store) => store.dispose(),
            ),
          ],
          child: kDebugMode
              ? MemoStackMarionetteE2eBridge(child: appChild)
              : appChild,
        );
      },
      home: const ColoredBox(
        color: Colors.transparent,
        child: AppShell(),
      ),
      debugShowCheckedModeBanner: false,
    );
  }
}
