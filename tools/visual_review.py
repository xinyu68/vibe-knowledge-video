"""Version-bound declarations of actual visual review, never an aesthetic classifier."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

from .project import ROOT, load, read_json, write_json

CHECKS = ('proportions_structure', 'pose_contact', 'occlusion_layers',
          'composition_readability', 'motion_continuity', 'character_anatomy')
OPTIONAL = {'pose_contact', 'motion_continuity', 'character_anatomy'}
LIMITATION = '校验审核声明、版本和证据完整性；不自动判断审美、人体比例，也不证明连续观看或试听。'


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def report_signature(report):
    # Re-previewing after production_ready changes only the technical source hash.
    # Every visual field, frame hash and motion-strip hash remains bound.
    data = {key: value for key, value in report.items() if key != 'source_sha256'}
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode('utf-8')).hexdigest()


def review_path(folder, config):
    return Path(folder) / config.get('output', 'build') / 'review' / 'visual-review.json'


def local_file(folder, name):
    if not isinstance(name, str) or not name.strip() or Path(name).is_absolute():
        raise ValueError('审核证据必须使用本期相对路径')
    path = (Path(folder) / name).resolve()
    if not path.is_relative_to(Path(folder).resolve()) or not path.is_file():
        raise ValueError(f'审核证据不存在或位于本期目录外: {name}')
    return path


def collect_evidence(folder, signature, paths):
    if not isinstance(paths, list) or not paths:
        raise ValueError('至少提供一份当前 preview / sample / animatic 的 layout_audit.json')
    reports, artifacts = [], {}
    for name in paths:
        path = local_file(folder, name)
        report = read_json(path)
        if not isinstance(report, dict) or report.get('visual_source_sha256') != signature:
            raise ValueError(f'视觉证据版本过期或缺少视觉签名，请重新 preview/sample: {name}')
        if report.get('layout_issue_frames') != 0:
            raise ValueError(f'先修复文字越界，再进行视觉审核: {name}')
        frames, strips = report.get('frames'), report.get('transition_strips', [])
        if not isinstance(frames, list) or not frames or not isinstance(strips, list):
            raise ValueError(f'视觉审核需要实际原尺寸 frame 证据: {name}')
        reports.append({'path': path.relative_to(Path(folder).resolve()).as_posix(),
                        'sha256': report_signature(report)})
        for kind, entries in [('frame', frames), ('motion_strip', strips)]:
            for item in entries:
                if not isinstance(item, dict) or not isinstance(item.get('file'), str):
                    raise ValueError(f'无效的图像证据条目: {name}')
                relative = (path.parent / item['file']).relative_to(Path(folder).resolve()).as_posix()
                picture = local_file(folder, relative)
                digest = sha256(picture)
                if item.get('sha256') != digest:
                    raise ValueError(f'图像证据哈希不符，需重新抽帧: {relative}')
                artifact = {'path': relative, 'sha256': digest, 'kind': kind}
                field = 'time' if kind == 'frame' else 'times'
                artifact[field] = item.get(field)
                artifacts[relative] = artifact
    return reports, list(artifacts.values())


def prepare_review(folder, config, visual_signature, evidence_paths, replace=False):
    folder = Path(folder).resolve()
    target = review_path(folder, config)
    if target.exists() and not replace:
        raise FileExistsError('审核记录已存在；返工后用 prepare --replace 备份旧记录并重置为未审')
    reports, evidence = collect_evidence(folder, visual_signature, list(evidence_paths))
    draft = {'schema_version': 1, 'visual_source_sha256': visual_signature,
             'reviewer': '', 'scope': '', 'contains_people': None,
             'evidence_reports': reports, 'evidence': evidence,
             'checks': {key: {'status': 'unreviewed', 'observation': '', 'evidence': []}
                        for key in CHECKS}, 'limitations': LIMITATION}
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        previous = target.parent / 'visual-review-history' / (sha256(target) + '.json')
        previous.parent.mkdir(exist_ok=True)
        previous.write_bytes(target.read_bytes())
    write_json(target, draft)
    return target


def filled(value):
    return isinstance(value, str) and bool(value.strip())


def validate_review(folder, config, visual_signature):
    folder = Path(folder).resolve()
    target = review_path(folder, config)
    result = {'ok': False, 'status': 'unreviewed', 'errors': [], 'limitations': LIMITATION}
    errors = result['errors']
    try:
        if not target.is_file():
            errors.append('缺少 visual-review.json：先 prepare，实际看图后填写审核')
            return result
        review = read_json(target)
        if not isinstance(review, dict) or review.get('schema_version') != 1:
            raise ValueError('无效的视觉审核 schema_version')
        if review.get('visual_source_sha256') != visual_signature:
            result['status'] = 'stale'
            errors.append('视觉源码版本已变化，旧审核失效；重新抽帧并 prepare --replace')
            return result
        records = review.get('evidence_reports')
        if not isinstance(records, list) or not records or any(not isinstance(r, dict) for r in records):
            raise ValueError('缺少 evidence_reports')
        reports, evidence = collect_evidence(folder, visual_signature, [r.get('path') for r in records])
        if reports != records or evidence != review.get('evidence'):
            result['status'] = 'stale'
            errors.append('证据报告或图像已变化，需重新审核')
            return result
        registered = {item['path']: item for item in evidence}
        for field in ('reviewer', 'scope'):
            if not filled(review.get(field)):
                errors.append(f'必须填写 {field}')
        people = review.get('contains_people')
        if not isinstance(people, bool):
            errors.append('contains_people 必须明确为 true / false')
        checks = review.get('checks')
        if not isinstance(checks, dict) or set(checks) != set(CHECKS):
            raise ValueError('checks 必须完整包含六项通用/按需审核')
        for key in CHECKS:
            item = checks[key]
            if not isinstance(item, dict):
                errors.append(f'{key}: 无效的审核条目')
                continue
            status = item.get('status')
            if status == 'not_applicable':
                if key not in OPTIONAL or (key == 'character_anatomy' and people is not False):
                    errors.append(f'{key}: 不允许 not_applicable')
                if not filled(item.get('observation')):
                    errors.append(f'{key}: 必须说明不适用的理由')
                continue
            if status != 'passed':
                errors.append(f'{key}: {status or "unreviewed"}，尚未通过')
                if status == 'needs_revision':
                    result['status'] = 'needs_revision'
                continue
            if not filled(item.get('observation')):
                errors.append(f'{key}: passed 必须有具体 observation')
            refs = item.get('evidence')
            if (not isinstance(refs, list) or not refs
                    or any(not isinstance(ref, str) or ref not in registered for ref in refs)):
                errors.append(f'{key}: 必须引用已登记的 evidence 图片路径')
            elif key in ('proportions_structure', 'character_anatomy') and not any(
                    registered[ref]['kind'] == 'frame' for ref in refs):
                errors.append(f'{key}: 必须查看原尺寸 frame，不能仅凭总览或动作缩略图')
            elif key == 'motion_continuity' and not any(
                    registered[ref]['kind'] == 'motion_strip' for ref in refs) and len({
                        registered[ref].get('time') for ref in refs}) < 3:
                errors.append(f'{key}: 需引用动作序列或至少三个时点的触发、过程、结果帧')
        if not errors:
            result.update({'ok': True, 'status': 'passed',
                           'receipt': target.relative_to(folder).as_posix(), 'sha256': sha256(target)})
    except (OSError, ValueError, TypeError, KeyError) as error:
        result['status'] = 'invalid'
        errors.append(str(error))
    return result


def require_visual_review(folder, config, visual_signature):
    folder = Path(folder).resolve()
    # Only the isolated synthetic self-test may skip creative review. A creative
    # episode cannot bypass the gate by setting test_only in videos/<slug>.
    if (folder.parent == (ROOT / '.local').resolve() and folder.name.startswith('self-test-')
            and config.get('test_only') is True):
        return {'ok': True, 'status': 'not_applicable', 'scope': 'technical_self_test'}
    report = validate_review(folder, config, visual_signature)
    if not report['ok']:
        raise ValueError('视觉审核未通过：' + '; '.join(report['errors']))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prepare = sub.add_parser('prepare', help='生成未审草稿，不自动批准')
    prepare.add_argument('slug')
    prepare.add_argument('--evidence', nargs='+', required=True, help='本期相对的 layout_audit.json 路径')
    prepare.add_argument('--replace', action='store_true', help='保留旧记录后重置审核')
    check = sub.add_parser('check', help='检查审核声明、证据与当前版本')
    check.add_argument('slug')
    args = parser.parse_args()
    folder, config, _ = load(args.slug)
    from .render import visual_source_signature
    signature = visual_source_signature(folder, config)
    if args.command == 'prepare':
        path = prepare_review(folder, config, signature, args.evidence, args.replace)
        print(f'已生成未审草稿: {path}\n实际查看证据后填写各项；本命令不执行视觉判断。')
        return
    report = validate_review(folder, config, signature)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report['ok']:
        raise SystemExit(1)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        raise SystemExit(1)
