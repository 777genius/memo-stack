String sidebarKeyPart(String value) {
  return value.replaceAll(RegExp(r'[^a-zA-Z0-9_]+'), '_');
}

String extractionStatusLabel(String status) {
  return switch (status) {
    'pending' => 'Pending',
    'running' => 'Running',
    'succeeded' => 'Ready',
    'failed' => 'Failed',
    'unsupported' => 'Unsupported',
    'canceled' => 'Canceled',
    'stale' => 'Stale',
    _ => status,
  };
}

String shortStorageId(String value) {
  if (value.length <= 10) return value;
  return '${value.substring(0, 6)}...${value.substring(value.length - 4)}';
}
