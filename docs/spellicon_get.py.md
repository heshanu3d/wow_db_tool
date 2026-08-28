# WoW 3.3.5a 获取技能图标

## 获取技能图标的完整链路

```text
技能 ID
  ↓
spell 表 / Spell.dbc
  ↓ SpellIconID
SpellIcon.dbc
  ↓ 根据 ID 找到 Name 字符串
Interface\Icons\xxx
  ↓ 拼接 .blp
Interface\Icons\xxx.blp
  ↓ BLP 解码
显示图标
```

## 七、适合当前 Python `db_tool` 的实现

`/usr1/test/code/wow/db_tool` 是 Python 项目，可以直接解析 WoW 3.3.5a build 12340 的 `SpellIcon.dbc`。

```python
from pathlib import Path
import struct


def load_spell_icon_dbc(dbc_file: str | Path) -> dict[int, str]:
    """
    读取 WoW 3.3.5a build 12340 的 SpellIcon.dbc。

    返回：
        {
            SpellIconID: "Interface\\Icons\\xxx",
            ...
        }
    """
    dbc_file = Path(dbc_file)
    data = dbc_file.read_bytes()

    if len(data) < 20:
        raise ValueError(f"DBC 文件太小: {dbc_file}")

    magic, record_count, field_count, record_size, string_block_size = (
        struct.unpack_from("<4s4I", data, 0)
    )

    if magic != b"WDBC":
        raise ValueError(
            f"不是标准 WDBC 文件，Magic={magic!r}: {dbc_file}"
        )

    # WoW 3.3.5a SpellIcon.dbc:
    # uint32 ID
    # uint32 NameOffset
    if field_count != 2 or record_size != 8:
        raise ValueError(
            "SpellIcon.dbc 结构不匹配: "
            f"field_count={field_count}, record_size={record_size}"
        )

    records_offset = 20
    strings_offset = records_offset + record_count * record_size
    strings_end = strings_offset + string_block_size

    if strings_end > len(data):
        raise ValueError(
            "SpellIcon.dbc 文件不完整: "
            f"需要 {strings_end} 字节，实际只有 {len(data)} 字节"
        )

    string_block = data[strings_offset:strings_end]
    icon_map: dict[int, str] = {}

    for index in range(record_count):
        record_offset = records_offset + index * record_size

        icon_id, name_offset = struct.unpack_from(
            "<II",
            data,
            record_offset,
        )

        if name_offset == 0:
            continue

        if name_offset >= len(string_block):
            continue

        string_end = string_block.find(b"\0", name_offset)
        if string_end == -1:
            continue

        icon_name = string_block[name_offset:string_end].decode(
            "utf-8",
            errors="replace",
        )

        icon_map[icon_id] = icon_name

    return icon_map
```

获取指定技能的图标路径：

```python
def get_spell_icon_path(
    spell_icon_id: int,
    icon_map: dict[int, str],
    extracted_client_root: str | Path,
) -> Path | None:
    icon_name = icon_map.get(int(spell_icon_id))

    if not icon_name:
        return None

    # DBC 内通常是 Windows/MPQ 风格路径：
    # Interface\\Icons\\Spell_Nature_xxx
    relative_path = icon_name.replace("\\", "/") + ".blp"

    return Path(extracted_client_root) / relative_path
```

使用示例：

```python
icon_map = load_spell_icon_dbc(
    "/path/to/DBFilesClient/SpellIcon.dbc"
)

spell_icon_id = 136  # 从 spell.SpellIconID 查询得到

blp_path = get_spell_icon_path(
    spell_icon_id,
    icon_map,
    "/path/to/extracted-wow-client",
)

if blp_path and blp_path.exists():
    print("技能图标:", blp_path)
else:
    print("技能图标不存在")
```

SQL 查询：

```python
cursor.execute(
    """
    SELECT SpellIconID, ActiveIconID
    FROM spell
    WHERE ID = %s
    LIMIT 1
    """,
    (spell_id,),
)

row = cursor.fetchone()

if row:
    spell_icon_id = row[0]
    active_icon_id = row[1]
```

## 八、图片资源的实际来源

`WoW-Spell-Editor` 不需要配置 WoW 客户端路径，也不会在运行时读取客户端 MPQ。

原因是官方发布的安装程序已经把技能图标和各版本的 `SpellIcon.dbc` 一起打包。安装目录中包含：

```text
WoW Spell Editor/
├── DBC_335_wotlk/
│   └── SpellIcon.dbc
└── Interface/
    └── Icons/
        ├── Ability_*.blp
        ├── INV_*.blp
        ├── Spell_*.blp
        └── ...
```

官方 v2.3.1 安装程序中包含：

```text
WoW Spell Editor/DBC_335_wotlk/SpellIcon.dbc
WoW Spell Editor/Interface/Icons/*.blp
```

其中共有约 6177 个 BLP 文件，解压后约 35.7 MB。

这些二进制图片没有提交在 Git 源代码仓库中，而是包含在 GitHub Release 的安装程序里。因此只克隆源码时看不到 `Interface/Icons`，安装官方发行版后才会出现。

### 为什么程序无需客户端路径

3.3.5a 的 `SpellIcon.dbc` 中保存的名称类似：

```text
Interface\Icons\Spell_Nature_Lightning
```

程序直接使用相对于当前工作目录的路径：

```csharp
File.Exists(icon + ".blp")
```

并直接打开：

```csharp
new FileStream(filePath, FileMode.Open)
```

所以程序实际读取的是安装目录中的：

```text
<WoW Spell Editor 安装目录>/Interface/Icons/xxx.blp
```

而不是 WoW 客户端目录中的文件。

`DBC_335_wotlk` 同样默认位于程序工作目录下：

```text
<WoW Spell Editor 安装目录>/DBC_335_wotlk/SpellIcon.dbc
```

### 用于 Python `db_tool` 的目录建议

可以从官方安装程序中提取以下两个资源：

```text
WoW Spell Editor/DBC_335_wotlk/SpellIcon.dbc
WoW Spell Editor/Interface/Icons/*.blp
```

然后放到：

```text
/usr1/test/code/wow/db_tool/assets/wow_335/
├── DBC_335_wotlk/
│   └── SpellIcon.dbc
└── Interface/
    └── Icons/
        └── *.blp
```

Linux 下可以使用 `7z` 从安装程序提取：

```bash
7z x WoW_Spell_Editor_v2_3_1.exe \
  'WoW Spell Editor/DBC_335_wotlk/SpellIcon.dbc' \
  'WoW Spell Editor/Interface/Icons/*' \
  -o./spell-editor-resources
```

在 Linux 下解析 DBC 路径时，还需要将反斜杠转换为目录分隔符：

```python
icon_name.replace("\\", "/")
```

## 九、原 C# 源码中需要注意的问题

原来的 `GetIconPath()` 使用：

```csharp
for (int i = 0; i < Header.RecordCount; ++i)
```

但实际访问的是：

```csharp
Lookups[i]
```

构建 `Lookups` 时会跳过 `Name offset == 0` 的记录，因此更安全的写法应该是：

```csharp
for (int i = 0; i < Lookups.Count; ++i)
```

图标数量较多时，最好直接使用字典：

```csharp
private readonly Dictionary<uint, string> _iconPaths =
    new Dictionary<uint, string>();
```

加载：

```csharp
_iconPaths[id] = name;
```

获取：

```csharp
public string GetIconPath(uint iconId)
{
    return _iconPaths.TryGetValue(iconId, out var path)
        ? path
        : "";
}
```

这样获取图标从逐条遍历的 `O(n)` 变成字典查询的 `O(1)`。

## 总结

WoW 3.3.5a 获取技能图标的核心步骤是：

1. 根据技能 ID 查询 `spell.SpellIconID`。
2. 使用 `SpellIconID` 查询 `SpellIcon.dbc`。
3. 从 DBC 字符串块中取得图标的 `Name` 路径。
4. 在路径后拼接 `.blp`。
5. 从客户端文件目录或 MPQ 中读取 BLP 文件。
6. 对 BLP 图片进行解码并显示。

原 C# 项目的核心调用为：

```csharp
string blpFile = spellIconDBC.GetIconPath(spellIconId) + ".blp";
```

然后通过：

```csharp
BlpManager.GetInstance().GetImageSourceFromBlpPath(blpFile)
```

完成 BLP 解码和显示。
