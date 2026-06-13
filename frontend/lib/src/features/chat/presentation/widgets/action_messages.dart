import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:frontend/src/presentation/theme/app_theme.dart';

List<List<dynamic>> groupChatMessages(List messages) {
  final groups = <List<dynamic>>[];
  List<dynamic>? currentActions;
  for (final m in messages) {
    if (m.kind == 'action') {
      final actionName = actionNameForMessage(m);
      final metaName = ((m.meta?['name'] as String?) ?? '').toLowerCase();
      if (actionName == 'screenshot' ||
          actionName == 'tool_result' ||
          metaName == 'tool_result' ||
          actionName.isEmpty) {
        continue;
      }

      currentActions ??= [];
      currentActions.add(m);
    } else {
      if (currentActions != null) {
        groups.add(currentActions);
        currentActions = null;
      }
      groups.add([m]);
    }
  }
  if (currentActions != null) groups.add(currentActions);
  return groups;
}

String actionNameForMessage(dynamic message) {
  final meta = (message.meta ?? const {}) as Map;
  final inner = (meta['meta'] is Map) ? (meta['meta'] as Map) : const {};
  final innerName = (inner['action'] as String?) ?? '';
  final metaName = (meta['name'] as String?) ?? '';
  return (innerName.isNotEmpty ? innerName : metaName).toLowerCase();
}

class ActionMessage extends StatelessWidget {
  final dynamic message;

  const ActionMessage({super.key, required this.message});

  @override
  Widget build(BuildContext context) {
    final actionName = actionNameForMessage(message);
    if (actionName == 'screenshot' ||
        actionName == 'tool_result' ||
        actionName.isEmpty) {
      return const SizedBox.shrink();
    }
    final status = (message.meta?['status'] as String? ?? '').toLowerCase();
    final badge = actionBadgeFor(context, actionName);
    final Color border = badge.$2;
    final Color fill = badge.$3;
    final IconData icon = badge.$1;
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 6),
        padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 10),
        decoration: BoxDecoration(
          color: fill,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: border),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 16, color: border),
            const SizedBox(width: 6),
            Container(
              padding: const EdgeInsets.symmetric(vertical: 2, horizontal: 6),
              decoration: BoxDecoration(
                color: border.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(6),
                border: Border.all(color: border.withValues(alpha: 0.4)),
              ),
              child: Text(
                status.isEmpty ? 'start' : status,
                style: Theme.of(context).textTheme.labelSmall,
              ),
            ),
            const SizedBox(width: 8),
            Flexible(
              child: Text(
                message.text ?? '',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class ActionGroup extends StatefulWidget {
  final List actions;

  const ActionGroup({super.key, required this.actions});

  @override
  State<ActionGroup> createState() => _ActionGroupState();
}

class _ActionGroupState extends State<ActionGroup> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    final count = widget.actions.length;
    final colorScheme = Theme.of(context).colorScheme;
    final badge = actionBadgeFor(context, _dominantActionName());

    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 6),
        decoration: BoxDecoration(
          color: badge.$3,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: badge.$2),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            InkWell(
              onTap: () => setState(() => _expanded = !_expanded),
              borderRadius: BorderRadius.circular(10),
              child: Padding(
                padding: const EdgeInsets.symmetric(
                  vertical: 8,
                  horizontal: 10,
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(badge.$1, size: 16, color: badge.$2),
                    const SizedBox(width: 6),
                    Text(
                      '$count actions',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            fontWeight: FontWeight.w600,
                          ),
                    ),
                    const SizedBox(width: 4),
                    Flexible(
                      child: Text(
                        _buildSummary(),
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                              color: colorScheme.onSurfaceVariant,
                            ),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    const SizedBox(width: 4),
                    Icon(
                      _expanded ? Icons.expand_less : Icons.expand_more,
                      size: 16,
                      color: colorScheme.onSurfaceVariant,
                    ),
                  ],
                ),
              ),
            ),
            if (_expanded)
              Padding(
                padding: const EdgeInsets.only(left: 10, right: 10, bottom: 8),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Divider(height: 8, thickness: 0.5),
                    for (var j = 0; j < widget.actions.length; j++)
                      _ActionRow(index: j + 1, message: widget.actions[j]),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }

  String _buildSummary() {
    final counts = <String, int>{};
    for (final m in widget.actions) {
      final action = actionNameForMessage(m);
      final label = _shortLabel(action);
      counts[label] = (counts[label] ?? 0) + 1;
    }
    return counts.entries.map((e) => '${e.value}× ${e.key}').join(', ');
  }

  String _dominantActionName() {
    final counts = <String, int>{};
    for (final m in widget.actions) {
      final action = actionNameForMessage(m);
      if (action.isNotEmpty) counts[action] = (counts[action] ?? 0) + 1;
    }
    if (counts.isEmpty) return '';
    return counts.entries.reduce((a, b) => a.value >= b.value ? a : b).key;
  }

  String _shortLabel(String action) {
    switch (action.toLowerCase()) {
      case 'left_click':
        return 'click';
      case 'double_click':
        return 'dblclick';
      case 'right_click':
        return 'rclick';
      case 'left_click_drag':
        return 'drag';
      case 'left_mouse_down':
        return 'mousedown';
      case 'left_mouse_up':
        return 'mouseup';
      case 'mouse_move':
        return 'move';
      case 'type':
        return 'type';
      case 'key':
      case 'hold_key':
        return 'key';
      case 'scroll':
        return 'scroll';
      case 'screenshot':
        return 'screenshot';
      default:
        return action;
    }
  }
}

class _ActionRow extends StatelessWidget {
  final int index;
  final dynamic message;

  const _ActionRow({required this.index, required this.message});

  @override
  Widget build(BuildContext context) {
    final meta = (message.meta ?? const {}) as Map;
    final inner = (meta['meta'] is Map) ? (meta['meta'] as Map) : const {};
    final action = ((inner['action'] as String?) ?? '').toLowerCase();
    final label = _formatClean(action, inner);
    final colorScheme = Theme.of(context).colorScheme;

    return InkWell(
      onTap: () => _showDetails(context, inner),
      borderRadius: BorderRadius.circular(6),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 3, horizontal: 4),
        child: Row(
          children: [
            Text(
              '$index.',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: colorScheme.onSurfaceVariant.withValues(alpha: 0.5),
                    fontSize: 11,
                  ),
            ),
            const SizedBox(width: 6),
            _iconWidget(action, colorScheme.onSurfaceVariant),
            const SizedBox(width: 6),
            Expanded(
              child: Text(label, style: Theme.of(context).textTheme.bodySmall),
            ),
            Icon(
              Icons.chevron_right,
              size: 14,
              color: colorScheme.onSurfaceVariant.withValues(alpha: 0.4),
            ),
          ],
        ),
      ),
    );
  }

  static Widget _iconWidget(String action, Color color) {
    const s = 14.0;
    if (action == 'left_click' || action == 'middle_click') {
      return Icon(Icons.ads_click, size: s, color: color);
    }
    if (action == 'double_click' || action == 'triple_click') {
      return Icon(Icons.touch_app, size: s, color: color);
    }
    if (action == 'right_click') {
      return Icon(Icons.more_horiz, size: s, color: color);
    }
    if (action == 'left_mouse_down' || action == 'left_mouse_up') {
      return Icon(Icons.ads_click, size: s, color: color);
    }
    if (action.contains('drag')) {
      return Icon(Icons.open_with, size: s, color: color);
    }
    if (action == 'mouse_move') {
      return Icon(Icons.near_me, size: s, color: color);
    }
    if (action == 'type') return Icon(Icons.keyboard, size: s, color: color);
    if (action == 'key' || action == 'hold_key') {
      return Icon(Icons.keyboard_command_key, size: s, color: color);
    }
    if (action == 'scroll') return Icon(Icons.swap_vert, size: s, color: color);
    if (action == 'screenshot') {
      return Icon(Icons.screenshot_monitor, size: s, color: color);
    }
    return Icon(Icons.build, size: s, color: color);
  }

  static String _formatClean(String action, Map inner) {
    if (action == 'screenshot') return 'Screenshot';
    if (action == 'mouse_move') return 'Move -> ${_coord(inner['coordinate'])}';
    if (action == 'left_click') return 'Click ${_coord(inner['coordinate'])}';
    if (action == 'double_click') {
      return 'Double click ${_coord(inner['coordinate'])}';
    }
    if (action == 'triple_click') {
      return 'Triple click ${_coord(inner['coordinate'])}';
    }
    if (action == 'right_click') {
      return 'Right click ${_coord(inner['coordinate'])}';
    }
    if (action == 'left_mouse_down') {
      return 'Mouse down ${_coord(inner['coordinate'])}';
    }
    if (action == 'left_mouse_up') {
      return 'Mouse up ${_coord(inner['coordinate'])}';
    }
    if (action == 'left_click_drag') {
      return 'Drag ${_coord(inner['start_coordinate'] ?? inner['start'])} -> ${_coord(inner['end_coordinate'] ?? inner['end'])}';
    }
    if (action == 'type') {
      final t = (inner['text'] as String?) ?? '';
      return 'Type "${t.length > 40 ? '${t.substring(0, 40)}...' : t}"';
    }
    if (action == 'key' || action == 'hold_key') {
      return 'Key ${(inner['key'] as String?) ?? (inner['text'] as String?) ?? ''}';
    }
    if (action == 'scroll') {
      return 'Scroll ${(inner['scroll_direction'] as String?) ?? 'down'} x${inner['scroll_amount'] ?? 1}';
    }
    if (action == 'wait') return 'Wait';
    return action.replaceAll('_', ' ');
  }

  static String _coord(dynamic c) {
    if (c is List && c.length >= 2) return '(${c[0]}, ${c[1]})';
    return '';
  }

  void _showDetails(BuildContext context, Map details) {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: Text('Action #$index', style: const TextStyle(fontSize: 16)),
        content: SingleChildScrollView(
          child: SelectableText(
            const JsonEncoder.withIndent('  ').convert(details),
            style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () {
              Clipboard.setData(
                ClipboardData(
                  text: const JsonEncoder.withIndent('  ').convert(details),
                ),
              );
              Navigator.pop(context);
            },
            child: const Text('Copy'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }
}

(IconData, Color, Color) actionBadgeFor(BuildContext context, String name) {
  final n = name.toLowerCase();
  if (n == 'screenshot') {
    return (
      Icons.screenshot_monitor,
      context.themeColors.actionTealBorder,
      context.themeColors.actionTealFill,
    );
  }
  if (n == 'mouse_move') {
    return (
      Icons.near_me,
      context.themeColors.actionIndigoBorder,
      context.themeColors.actionIndigoFill,
    );
  }
  if (n == 'left_click' ||
      n == 'double_click' ||
      n == 'triple_click' ||
      n == 'right_click' ||
      n == 'middle_click') {
    return (
      Icons.ads_click,
      context.themeColors.actionPurpleBorder,
      context.themeColors.actionPurpleFill,
    );
  }
  if (n == 'left_mouse_down' || n == 'left_mouse_up') {
    return (
      Icons.ads_click,
      context.themeColors.actionPurpleBorder,
      context.themeColors.actionPurpleFill,
    );
  }
  if (n == 'left_click_drag') {
    return (
      Icons.open_with,
      context.themeColors.actionPurpleBorder,
      context.themeColors.actionPurpleFill,
    );
  }
  if (n == 'type') {
    return (
      Icons.keyboard,
      context.themeColors.actionBlueGreyBorder,
      context.themeColors.actionBlueGreyFill,
    );
  }
  if (n == 'key' || n == 'hold_key') {
    return (
      Icons.keyboard_command_key,
      context.themeColors.actionBlueGreyBorder,
      context.themeColors.actionBlueGreyFill,
    );
  }
  if (n == 'scroll') {
    return (
      Icons.swap_vert,
      context.themeColors.actionGreenBorder,
      context.themeColors.actionGreenFill,
    );
  }
  if (n == 'wait') {
    return (
      Icons.hourglass_empty,
      context.themeColors.actionOrangeBorder,
      context.themeColors.actionOrangeFill,
    );
  }
  return (
    Icons.build,
    context.themeColors.actionPurpleBorder,
    context.themeColors.actionPurpleFill,
  );
}
