from ..github import source_path


def inspect_patch(pr, args):
    if args.path is None:
        return {'diff': pr.diff, 'available_files': sorted(pr.sources)}
    if not source_path(args.path) or args.path not in pr.sources:
        raise ValueError('Source file is not available or allowlisted')
    lines = pr.sources[args.path].splitlines()
    begin = args.start_line - 1
    return {'path': args.path, 'start_line': args.start_line,
            'source': '\n'.join(lines[begin:begin + args.max_lines])}
