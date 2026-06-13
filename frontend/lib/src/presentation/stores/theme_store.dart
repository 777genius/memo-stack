import 'package:flutter/material.dart';

class ThemeStore extends ChangeNotifier {
  ThemeMode mode = ThemeMode.system;
  void setMode(ThemeMode m) {
    if (m == mode) return;
    mode = m;
    notifyListeners();
  }

  void toggleUsing(BuildContext context) {
    // Переключаем по фактической яркости сейчас, чтобы не нажимать 2 раза при system
    final isDark = Theme.of(context).brightness == Brightness.dark;
    setMode(isDark ? ThemeMode.light : ThemeMode.dark);
  }
}
