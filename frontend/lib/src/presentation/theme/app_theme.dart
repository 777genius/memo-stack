import 'package:flutter/material.dart';

class AppThemeColors extends ThemeExtension<AppThemeColors> {
  final Color userBubbleBg;
  final Color userBubbleFg;
  final Color assistantBubbleBg;
  final Color assistantBubbleFg;
  final Color surfaceBorder;

  final Color usageBorder;
  final Color usageFill;

  final Color actionTealBorder;
  final Color actionTealFill;
  final Color actionIndigoBorder;
  final Color actionIndigoFill;
  final Color actionPurpleBorder;
  final Color actionPurpleFill;
  final Color actionBlueGreyBorder;
  final Color actionBlueGreyFill;
  final Color actionGreenBorder;
  final Color actionGreenFill;
  final Color actionOrangeBorder;
  final Color actionOrangeFill;

  const AppThemeColors({
    required this.userBubbleBg,
    required this.userBubbleFg,
    required this.assistantBubbleBg,
    required this.assistantBubbleFg,
    required this.surfaceBorder,
    required this.usageBorder,
    required this.usageFill,
    required this.actionTealBorder,
    required this.actionTealFill,
    required this.actionIndigoBorder,
    required this.actionIndigoFill,
    required this.actionPurpleBorder,
    required this.actionPurpleFill,
    required this.actionBlueGreyBorder,
    required this.actionBlueGreyFill,
    required this.actionGreenBorder,
    required this.actionGreenFill,
    required this.actionOrangeBorder,
    required this.actionOrangeFill,
  });

  @override
  ThemeExtension<AppThemeColors> copyWith({
    Color? userBubbleBg,
    Color? userBubbleFg,
    Color? assistantBubbleBg,
    Color? assistantBubbleFg,
    Color? surfaceBorder,
    Color? usageBorder,
    Color? usageFill,
    Color? actionTealBorder,
    Color? actionTealFill,
    Color? actionIndigoBorder,
    Color? actionIndigoFill,
    Color? actionPurpleBorder,
    Color? actionPurpleFill,
    Color? actionBlueGreyBorder,
    Color? actionBlueGreyFill,
    Color? actionGreenBorder,
    Color? actionGreenFill,
    Color? actionOrangeBorder,
    Color? actionOrangeFill,
  }) {
    return AppThemeColors(
      userBubbleBg: userBubbleBg ?? this.userBubbleBg,
      userBubbleFg: userBubbleFg ?? this.userBubbleFg,
      assistantBubbleBg: assistantBubbleBg ?? this.assistantBubbleBg,
      assistantBubbleFg: assistantBubbleFg ?? this.assistantBubbleFg,
      surfaceBorder: surfaceBorder ?? this.surfaceBorder,
      usageBorder: usageBorder ?? this.usageBorder,
      usageFill: usageFill ?? this.usageFill,
      actionTealBorder: actionTealBorder ?? this.actionTealBorder,
      actionTealFill: actionTealFill ?? this.actionTealFill,
      actionIndigoBorder: actionIndigoBorder ?? this.actionIndigoBorder,
      actionIndigoFill: actionIndigoFill ?? this.actionIndigoFill,
      actionPurpleBorder: actionPurpleBorder ?? this.actionPurpleBorder,
      actionPurpleFill: actionPurpleFill ?? this.actionPurpleFill,
      actionBlueGreyBorder: actionBlueGreyBorder ?? this.actionBlueGreyBorder,
      actionBlueGreyFill: actionBlueGreyFill ?? this.actionBlueGreyFill,
      actionGreenBorder: actionGreenBorder ?? this.actionGreenBorder,
      actionGreenFill: actionGreenFill ?? this.actionGreenFill,
      actionOrangeBorder: actionOrangeBorder ?? this.actionOrangeBorder,
      actionOrangeFill: actionOrangeFill ?? this.actionOrangeFill,
    );
  }

  @override
  ThemeExtension<AppThemeColors> lerp(
      ThemeExtension<AppThemeColors>? other, double t) {
    if (other is! AppThemeColors) return this;
    return AppThemeColors(
      userBubbleBg: Color.lerp(userBubbleBg, other.userBubbleBg, t)!,
      userBubbleFg: Color.lerp(userBubbleFg, other.userBubbleFg, t)!,
      assistantBubbleBg:
          Color.lerp(assistantBubbleBg, other.assistantBubbleBg, t)!,
      assistantBubbleFg:
          Color.lerp(assistantBubbleFg, other.assistantBubbleFg, t)!,
      surfaceBorder: Color.lerp(surfaceBorder, other.surfaceBorder, t)!,
      usageBorder: Color.lerp(usageBorder, other.usageBorder, t)!,
      usageFill: Color.lerp(usageFill, other.usageFill, t)!,
      actionTealBorder:
          Color.lerp(actionTealBorder, other.actionTealBorder, t)!,
      actionTealFill: Color.lerp(actionTealFill, other.actionTealFill, t)!,
      actionIndigoBorder:
          Color.lerp(actionIndigoBorder, other.actionIndigoBorder, t)!,
      actionIndigoFill:
          Color.lerp(actionIndigoFill, other.actionIndigoFill, t)!,
      actionPurpleBorder:
          Color.lerp(actionPurpleBorder, other.actionPurpleBorder, t)!,
      actionPurpleFill:
          Color.lerp(actionPurpleFill, other.actionPurpleFill, t)!,
      actionBlueGreyBorder:
          Color.lerp(actionBlueGreyBorder, other.actionBlueGreyBorder, t)!,
      actionBlueGreyFill:
          Color.lerp(actionBlueGreyFill, other.actionBlueGreyFill, t)!,
      actionGreenBorder:
          Color.lerp(actionGreenBorder, other.actionGreenBorder, t)!,
      actionGreenFill: Color.lerp(actionGreenFill, other.actionGreenFill, t)!,
      actionOrangeBorder:
          Color.lerp(actionOrangeBorder, other.actionOrangeBorder, t)!,
      actionOrangeFill:
          Color.lerp(actionOrangeFill, other.actionOrangeFill, t)!,
    );
  }
}

class AppThemeStyles extends ThemeExtension<AppThemeStyles> {
  final TextStyle body;
  final TextStyle bodySmall;
  final TextStyle caption;
  final TextStyle labelSmall;

  const AppThemeStyles({
    required this.body,
    required this.bodySmall,
    required this.caption,
    required this.labelSmall,
  });

  @override
  ThemeExtension<AppThemeStyles> copyWith({
    TextStyle? body,
    TextStyle? bodySmall,
    TextStyle? caption,
    TextStyle? labelSmall,
  }) {
    return AppThemeStyles(
      body: body ?? this.body,
      bodySmall: bodySmall ?? this.bodySmall,
      caption: caption ?? this.caption,
      labelSmall: labelSmall ?? this.labelSmall,
    );
  }

  @override
  ThemeExtension<AppThemeStyles> lerp(
      ThemeExtension<AppThemeStyles>? other, double t) {
    if (other is! AppThemeStyles) return this;
    return AppThemeStyles(
      body: TextStyle.lerp(body, other.body, t)!,
      bodySmall: TextStyle.lerp(bodySmall, other.bodySmall, t)!,
      caption: TextStyle.lerp(caption, other.caption, t)!,
      labelSmall: TextStyle.lerp(labelSmall, other.labelSmall, t)!,
    );
  }
}

class AppTheme {
  final AppThemeColors colors;
  final AppThemeStyles styles;
  const AppTheme(this.colors, this.styles);

  TextStyle style(
      TextStyle Function(AppThemeStyles) s, Color Function(AppThemeColors) c) {
    return s(styles).copyWith(color: c(colors));
  }
}

extension AppThemeContextExt on BuildContext {
  AppTheme get theme {
    final colors = Theme.of(this).extension<AppThemeColors>();
    final styles = Theme.of(this).extension<AppThemeStyles>();
    return AppTheme(colors!, styles!);
  }

  AppThemeColors get themeColors => Theme.of(this).extension<AppThemeColors>()!;
  AppThemeStyles get themeStyles => Theme.of(this).extension<AppThemeStyles>()!;
}
