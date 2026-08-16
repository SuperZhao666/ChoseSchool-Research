UPDATE evidence_sources
SET title = '中国海洋大学2026年硕士研究生招生专业目录（更新版）',
    institution = '中国海洋大学',
    source_note = '2026正式目录按培养单位、专业和方向列示考试科目与统考计划。',
    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
WHERE url = 'https://yz.ouc.edu.cn/_upload/article/files/5d/fc/57e7f1504eacae254287e9a880fc/07881f5e-0591-4013-ab5e-b167da6d4a35.xls'
  AND content_sha256 = '092c5f4fbb9dfbe155e1c04d4c36bc83042a4fd0a8c5ab9113d534adc6b02108';

UPDATE evidence_sources
SET title = '中国海洋大学2026年硕士研究生进入复试的初试成绩要求',
    institution = '中国海洋大学',
    source_note = '官方复试线按培养单位、专业和方向分列。',
    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
WHERE url = 'https://yz.ouc.edu.cn/_upload/article/files/ee/92/44c4f3e74993b19437d6078498b2/1636a55c-2149-4a61-b9f4-c1f78dab1a06.pdf'
  AND content_sha256 = '5062dc5d05023f17ee8cf7f9c598d20b82f1105c491f52d3362b15a659ed1a43';

UPDATE evidence_sources
SET title = '中国海洋大学2026年全日制研究生学费与学制标准',
    institution = '中国海洋大学',
    source_note = '官方收费表列示全日制专业学位学费与标准学制。',
    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
WHERE url = 'https://dxb.ouc.edu.cn/_upload/article/files/ae/3b/25b0a2b7448ebd6d5366b94847d2/d63b16dd-eff3-4910-be35-555615eaa246.pdf'
  AND content_sha256 = 'd39a5a63fff22b3aa198f489c6e89f4a26044ee13775a807ab598d2026a7979b';

UPDATE evidence_sources
SET title = '卓越工程师学院2026年硕士研究生复试录取工作实施细则',
    institution = '中国海洋大学卓越工程师学院',
    source_note = '学院细则列示复试阶段计划、初复试权重和纯面试制度。',
    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
WHERE url = 'https://gcee.ouc.edu.cn/2026/0320/c32719a522816/page.htm'
  AND content_sha256 = '122985a1fb4d353270deb4abe17bb8bd5b0eb1b4382fdfbdd2c7dae4adc9b75a';

UPDATE evidence_sources
SET title = '卓越工程师学院2026年硕士研究生一志愿复试名单',
    institution = '中国海洋大学卓越工程师学院',
    source_note = '官方名单按专业列示一志愿全日制复试考生，备注列为空。',
    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
WHERE url = 'https://gcee.ouc.edu.cn/_upload/article/files/40/ac/4adb816b4c5690b76c5b3b840a1f/fd4ee577-8500-4d7e-8c17-3c350bdea8d1.pdf'
  AND content_sha256 = 'd6f653489172b4d6c571168808872fb11646df886211dd42152a3ca9714881a1';

INSERT INTO audit_events(trace_id, event_type, entity_type, entity_id, payload_json, created_at)
SELECT
    'migration-010-repair-ouc-source-metadata',
    'evidence_metadata_repaired',
    'evidence_source_set',
    'ouc-2026-official-sources',
    '{"reason":"repair PowerShell pipeline encoding damage","scope":"titles institutions and source notes only"}',
    strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
WHERE EXISTS (
    SELECT 1 FROM evidence_sources
    WHERE url = 'https://gcee.ouc.edu.cn/2026/0320/c32719a522816/page.htm'
      AND content_sha256 = '122985a1fb4d353270deb4abe17bb8bd5b0eb1b4382fdfbdd2c7dae4adc9b75a'
);
