const workspacePaths = new Set(['/workbench', '/knowledge', '/graph', '/dsl'])

export function getStaffDestination(value) {
  if (typeof value !== 'string' || /[\\\u0000-\u0020\u007f]/.test(value)) {
    return '/knowledge'
  }
  const path = value.split(/[?#]/, 1)[0]
  return workspacePaths.has(path) ? value : '/knowledge'
}
