// dart format width=80
// GENERATED CODE - DO NOT MODIFY BY HAND

// **************************************************************************
// InjectableConfigGenerator
// **************************************************************************

// ignore_for_file: type=lint
// coverage:ignore-file

// ignore_for_file: no_leading_underscores_for_library_prefixes
import 'package:dio/dio.dart' as _i361;
import 'package:frontend/src/app/di/app_module.dart' as _i136;
import 'package:frontend/src/app/services/api_key_validator.dart' as _i540;
import 'package:frontend/src/app/services/auto_updater_service.dart' as _i725;
import 'package:frontend/src/app/services/secure_storage_service.dart' as _i428;
import 'package:frontend/src/features/chat/application/usecases/run_task_usecase.dart'
    as _i609;
import 'package:frontend/src/features/chat/data/datasources/backend_rest_client.dart'
    as _i18;
import 'package:frontend/src/features/chat/data/datasources/backend_ws_client.dart'
    as _i1053;
import 'package:frontend/src/features/chat/data/repositories/chat_repository_impl.dart'
    as _i921;
import 'package:frontend/src/features/chat/domain/repositories/chat_repository.dart'
    as _i984;
import 'package:get_it/get_it.dart' as _i174;
import 'package:injectable/injectable.dart' as _i526;

extension GetItInjectableX on _i174.GetIt {
// initializes the registration of main-scope dependencies inside of GetIt
  _i174.GetIt init({
    String? environment,
    _i526.EnvironmentFilter? environmentFilter,
  }) {
    final gh = _i526.GetItHelper(
      this,
      environment,
      environmentFilter,
    );
    final appModule = _$AppModule();
    gh.lazySingleton<_i361.Dio>(() => appModule.dio);
    gh.lazySingleton<_i540.ApiKeyValidator>(() => _i540.ApiKeyValidator());
    gh.lazySingleton<_i428.SecureStorageService>(
        () => _i428.SecureStorageService());
    gh.lazySingleton<_i18.BackendRestClient>(() => _i18.BackendRestClient());
    gh.lazySingleton<_i1053.BackendWsClient>(() => _i1053.BackendWsClient());
    gh.lazySingleton<_i984.ChatRepository>(
        () => _i921.ChatRepositoryImpl(gh<_i18.BackendRestClient>()));
    gh.lazySingleton<_i725.AutoUpdaterService>(
        () => _i725.AutoUpdaterService(gh<_i361.Dio>()));
    gh.factory<_i609.RunTaskUseCase>(
        () => _i609.RunTaskUseCase(gh<_i984.ChatRepository>()));
    return this;
  }
}

class _$AppModule extends _i136.AppModule {}
