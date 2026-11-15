-- Blueprint Lib --
-- Creative-only blueprint library tool: folders / tags / favorites / hidden flags kept in the mod's
-- own Data/library.json (keyed by blueprint localId). Original blueprint files are only read.
--   RMB / R : open library (RMB cancels while placing)
--   LMB     : place selected blueprint
--   Q       : rotate             F : change spawn height

dofile( "$GAME_DATA/Scripts/game/AnimationUtil.lua" )
dofile( "$SURVIVAL_DATA/Scripts/blueprint_util.lua" )

BlueprintLib = class()

local INDEX_PATH = "$CONTENT_DATA/Data/index.json"
local LIBRARY_PATH = "$CONTENT_DATA/Data/library.json"
local REQUEST_PATH = "$CONTENT_DATA/Data/request.json" -- written by the web manager ("place in game")
local REQUEST_POLL_TICKS = 40                              -- 1 s
local LAYOUT_PATH = "$CONTENT_DATA/Gui/Layouts/BlueprintLib.layout"
local EMPTY_IMAGE = "$CONTENT_DATA/Gui/empty.png"
local CHECK_IMAGE = "$CONTENT_DATA/Gui/check.png"
local WARN_IMAGE = "$CONTENT_DATA/Gui/warn.png"

-- must match tools/gen_layout.py
local VIEWS = {
	L = { size = 12, panel = "ViewLPanel" },
	G = { size = 24, panel = "ViewGPanel" },
	R = { size = 10, panel = "ViewRPanel", list = true }
}
local VIEW_ORDER = { "L", "G", "R" }
local FOLDER_ROWS = 12
local CHIP_COUNT = 8

local PLACE_RANGE = 50.0
local HEIGHTS = { 0.5, 1.0, 2.0, 4.0, 8.0, 0.25 } -- metres above the aimed surface (F cycles)
local DOUBLE_CLICK_TICKS = 12                     -- 0.3 s
local MAX_NAME_BYTES = 240      -- full folder path
local MAX_TAG_BYTES = 96
local RECENT_LIMIT = 60

local S_ALL, S_FAV, S_RECENT, S_UNFILED, S_WORKSHOP, S_HIDDEN = "*all", "*fav", "*recent", "*unfiled", "*workshop", "*hidden"
local S_MISSING = "*missing" -- blueprints whose mods are not loaded in this world
local SORTS = { "new", "old", "name", "used" }

local renderables = { "$GAME_DATA/Character/Char_Tools/Char_liftremote/char_liftremote.rend" }
local renderablesTp = { "$GAME_DATA/Character/Char_Male/Animations/char_male_tp_weldtool.rend", "$GAME_DATA/Character/Char_Tools/Char_liftremote/char_liftremote_tp_animlist.rend" }
local renderablesFp = { "$GAME_DATA/Character/Char_Tools/Char_liftremote/char_liftremote_fp_animlist.rend" }
sm.tool.preloadRenderables( renderables )
sm.tool.preloadRenderables( renderablesTp )
sm.tool.preloadRenderables( renderablesFp )

local Rotations = {
	sm.quat.new( 0, 0, 0, 1 ),
	sm.quat.new( 0, 0, 0.70710678118654752, 0.70710678118654752 ),
	sm.quat.new( 0, 0, 1, 0 ),
	sm.quat.new( 0, 0, -0.70710678118654752, 0.70710678118654752 )
}

----------------------------------------------------------------------------------------------------
-- Text
----------------------------------------------------------------------------------------------------
local Texts = {
	Japanese = {
		tabFolders = "フォルダ", tabTags = "タグ",
		all = "すべて", fav = "お気に入り", recent = "最近使った", unfiled = "未分類", workshop = "Workshop", hidden = "非表示",
		create = "作成", rename = "名前変更", delete = "削除", reload = "再読込",
		viewL = "大", viewG = "中", viewR = "一覧",
		sort = { new = "新しい順", old = "古い順", name = "名前順", used = "使用順" },
		selectMode = "複数選択", selectAll = "全選択", selectNone = "解除",
		tagHeader = "タグ（クリックで外す）", addTag = "追加",
		dropMode = "左の一覧へ入れる…", dropModeOn = "入れ先を左でクリック",
		dropHint = "▼ 入れ先をクリック",
		unfile = "フォルダ解除", favOn = "お気に入り解除", favOff = "お気に入り", hideOn = "再表示", hideOff = "非表示",
		place = "設置",
		count = "%d 件", countSel = "%d 件 / %d 件選択", noSelection = "未選択", multiSel = "%d 件を選択中",
		folderLabel = "フォルダ: %s", mixed = "（混在）", none = "なし",
		srcLocal = "ローカル", srcWorkshop = "Workshop",
		creativeOnly = "Blueprint Lib はクリエイティブ専用です",
		noIndex = "ブループリント一覧がありません。Blueprint Lib Manager を起動して「再スキャン」してください",
		indexLoaded = "%d 件のブループリントを読み込みました",
		loadFailed = "ブループリントを読み込めませんでした", previewFailed = "プレビューを作れませんでした（MOD不足の可能性）",
		placed = "設置しました: %s", placeFailed = "設置に失敗しました: %s",
		hintPlace = "設置", hintRotate = "回転", hintHeight = "高さ %sm", hintCancel = "キャンセル", hintOpen = "ライブラリを開く",
		needFolder = "左の一覧でユーザーフォルダを選んでください", folderExists = "同じ名前のフォルダがあります",
		badName = "フォルダ名が不正です（空の階層 / * や # で始まる / 長すぎる）", badTag = "タグが不正です",
		folderDeleted = "フォルダを削除しました（中身は未分類に戻ります）", folderRenamed = "フォルダを「%s」に変更しました",
		folderCreated = "フォルダ「%s」を作成しました", folderDeletedUp = "フォルダを削除しました（中身は「%s」へ移動）",
		cantMoveIntoSelf = "フォルダを自分の中には移動できません",
		modeDynamic = "物理あり", modeStatic = "固定（静的）", hintMode = "物理/固定",
		placeSeq = "順に設置 (%d)", remotePlace = "ブラウザから: %s を設置モードにしました",
		externalChange = "ブラウザ側で変更されていたため読み込み直しました（直前の操作は反映されていません）", queueDone = "選択したものをすべて設置しました",
		placedFrozen = "設置しました: %s  ※ %d/%d 個のボディが固定状態です",
		missingFolder = "設置不可（MOD不足）", missingShort = "[MOD不足]",
		missingMods = "MOD不足: %s", skipMissing = "%d 件はMOD不足のため飛ばします（%s）",
		placeDisabled = "MOD不足で設置できません", cantPlace = "%s は設置できません（MOD不足: %s）",
		nothingSelected = "ブループリントを選んでください",
		dropped = "%d 件を「%s」へ入れました", dropUnfiled = "%d 件をフォルダから外しました",
		dropFav = "%d 件をお気に入りにしました", dropHidden = "%d 件を非表示にしました", dropShown = "%d 件を再表示しました",
		dropTag = "%d 件にタグ「%s」を付けました", dropInvalid = "ここには入れられません",
		tagAdded = "%d 件にタグ「%s」を付けました", tagRemoved = "%d 件からタグ「%s」を外しました",
		selectedAll = "%d 件を選択しました"
	},
	English = {
		tabFolders = "Folders", tabTags = "Tags",
		all = "All", fav = "Favorites", recent = "Recent", unfiled = "Unfiled", workshop = "Workshop", hidden = "Hidden",
		create = "Create", rename = "Rename", delete = "Delete", reload = "Reload",
		viewL = "L", viewG = "M", viewR = "List",
		sort = { new = "Newest", old = "Oldest", name = "Name", used = "Last used" },
		selectMode = "Multi", selectAll = "All", selectNone = "None",
		tagHeader = "Tags (click to remove)", addTag = "Add",
		dropMode = "Put into...", dropModeOn = "Click a target on the left",
		dropHint = "Click a target",
		unfile = "Unfile", favOn = "Unfavorite", favOff = "Favorite", hideOn = "Unhide", hideOff = "Hide",
		place = "PLACE",
		count = "%d items", countSel = "%d items / %d selected", noSelection = "Nothing selected", multiSel = "%d selected",
		folderLabel = "Folder: %s", mixed = "(mixed)", none = "none",
		srcLocal = "Local", srcWorkshop = "Workshop",
		creativeOnly = "Blueprint Lib only works in Creative",
		noIndex = "No blueprint list yet. Start Blueprint Lib Manager and press Rescan",
		indexLoaded = "Loaded %d blueprints",
		loadFailed = "Could not load the blueprint", previewFailed = "Could not build a preview (missing mods?)",
		placed = "Placed: %s", placeFailed = "Placement failed: %s",
		hintPlace = "Place", hintRotate = "Rotate", hintHeight = "Height %sm", hintCancel = "Cancel", hintOpen = "Open library",
		needFolder = "Select a user folder on the left first", folderExists = "A folder with that name exists",
		badName = "Invalid folder name (empty level / starts with * or # / too long)", badTag = "Invalid tag",
		folderDeleted = "Folder deleted (its blueprints are unfiled again)", folderRenamed = "Folder is now \"%s\"",
		folderCreated = "Created folder \"%s\"", folderDeletedUp = "Folder deleted (its blueprints moved to \"%s\")",
		cantMoveIntoSelf = "A folder can't be moved into itself",
		modeDynamic = "Physics", modeStatic = "Fixed (static)", hintMode = "Physics/Fixed",
		placeSeq = "PLACE ALL (%d)", remotePlace = "From browser: placing %s",
		externalChange = "The library was changed in the browser and has been reloaded (your last edit was not applied)", queueDone = "Placed every selected blueprint",
		placedFrozen = "Placed: %s  (%d/%d bodies are frozen)",
		missingFolder = "Can't place (missing mods)", missingShort = "[MISSING MODS]",
		missingMods = "Missing mods: %s", skipMissing = "%d will be skipped, missing mods (%s)",
		placeDisabled = "MISSING MODS", cantPlace = "%s can't be placed (missing mods: %s)",
		nothingSelected = "Select blueprints first",
		dropped = "Put %d into \"%s\"", dropUnfiled = "Removed %d from their folders",
		dropFav = "Favorited %d", dropHidden = "Hid %d", dropShown = "Unhid %d",
		dropTag = "Tagged %d with \"%s\"", dropInvalid = "Can't put blueprints there",
		tagAdded = "Tagged %d with \"%s\"", tagRemoved = "Removed from %d: \"%s\"",
		selectedAll = "Selected %d"
	},
	Korean = {
		tabFolders = "폴더", tabTags = "태그",
		all = "전체", fav = "즐겨찾기", recent = "최근 사용", unfiled = "미분류", workshop = "Workshop", hidden = "숨김",
		create = "만들기", rename = "이름 변경", delete = "삭제", reload = "새로고침",
		viewL = "대", viewG = "중", viewR = "목록",
		sort = { new = "최신순", old = "오래된순", name = "이름순", used = "사용순" },
		selectMode = "다중 선택", selectAll = "전체 선택", selectNone = "선택 해제",
		tagHeader = "태그 (클릭하여 제거)", addTag = "추가",
		dropMode = "왼쪽 목록에 넣기…", dropModeOn = "왼쪽에서 대상을 클릭",
		dropHint = "▼ 대상을 클릭",
		unfile = "폴더에서 빼기", favOn = "즐겨찾기 해제", favOff = "즐겨찾기", hideOn = "다시 표시", hideOff = "숨기기",
		place = "설치",
		count = "%d개", countSel = "%d개 / %d개 선택", noSelection = "선택 안 됨", multiSel = "%d개 선택됨",
		folderLabel = "폴더: %s", mixed = "(혼합)", none = "없음",
		srcLocal = "로컬", srcWorkshop = "Workshop",
		creativeOnly = "Blueprint Lib는 크리에이티브 전용입니다",
		noIndex = "블루프린트 목록이 없습니다. Blueprint Lib Manager를 실행하고 「다시 스캔」을 누르세요",
		indexLoaded = "블루프린트 %d개를 불러왔습니다",
		loadFailed = "블루프린트를 불러올 수 없습니다", previewFailed = "미리보기를 만들 수 없습니다 (MOD 부족 가능성)",
		placed = "설치했습니다: %s", placeFailed = "설치에 실패했습니다: %s",
		hintPlace = "설치", hintRotate = "회전", hintHeight = "높이 %sm", hintCancel = "취소", hintOpen = "라이브러리 열기",
		needFolder = "왼쪽 목록에서 사용자 폴더를 선택하세요", folderExists = "같은 이름의 폴더가 있습니다",
		badName = "잘못된 폴더 이름입니다 (빈 단계 / * 또는 #로 시작 / 너무 김)", badTag = "잘못된 태그입니다",
		folderDeleted = "폴더를 삭제했습니다 (내용은 미분류로 돌아갑니다)", folderRenamed = "폴더 이름을 「%s」(으)로 변경했습니다",
		folderCreated = "폴더 「%s」을(를) 만들었습니다", folderDeletedUp = "폴더를 삭제했습니다 (내용은 「%s」(으)로 이동)",
		cantMoveIntoSelf = "폴더를 자기 자신 안으로 옮길 수 없습니다",
		modeDynamic = "물리 적용", modeStatic = "고정 (정적)", hintMode = "물리/고정",
		placeSeq = "순서대로 설치 (%d)", remotePlace = "브라우저에서: %s 설치 모드로 전환했습니다",
		externalChange = "브라우저에서 변경되어 다시 불러왔습니다 (직전 작업은 반영되지 않았습니다)", queueDone = "선택한 항목을 모두 설치했습니다",
		placedFrozen = "설치했습니다: %s  ※ 바디 %d/%d개가 고정 상태입니다",
		missingFolder = "설치 불가 (MOD 부족)", missingShort = "[MOD 부족]",
		missingMods = "MOD 부족: %s", skipMissing = "%d개는 MOD 부족으로 건너뜁니다 (%s)",
		placeDisabled = "MOD 부족으로 설치할 수 없습니다", cantPlace = "%s은(는) 설치할 수 없습니다 (MOD 부족: %s)",
		nothingSelected = "블루프린트를 선택하세요",
		dropped = "%d개를 「%s」에 넣었습니다", dropUnfiled = "%d개를 폴더에서 뺐습니다",
		dropFav = "%d개를 즐겨찾기에 추가했습니다", dropHidden = "%d개를 숨겼습니다", dropShown = "%d개를 다시 표시했습니다",
		dropTag = "%d개에 태그 「%s」을(를) 붙였습니다", dropInvalid = "여기에는 넣을 수 없습니다",
		tagAdded = "%d개에 태그 「%s」을(를) 붙였습니다", tagRemoved = "%d개에서 태그 「%s」을(를) 제거했습니다",
		selectedAll = "%d개를 선택했습니다"
	},
	Chinese = { -- Simplified Chinese (the game's "Chinese" language)
		tabFolders = "文件夹", tabTags = "标签",
		all = "全部", fav = "收藏", recent = "最近使用", unfiled = "未分类", workshop = "创意工坊", hidden = "隐藏",
		create = "新建", rename = "重命名", delete = "删除", reload = "重新载入",
		viewL = "大", viewG = "中", viewR = "列表",
		sort = { new = "最新", old = "最早", name = "名称", used = "最近使用" },
		selectMode = "多选", selectAll = "全选", selectNone = "取消选择",
		tagHeader = "标签（点击移除）", addTag = "添加",
		dropMode = "放入左侧列表…", dropModeOn = "在左侧点击目标",
		dropHint = "▼ 点击目标",
		unfile = "移出文件夹", favOn = "取消收藏", favOff = "收藏", hideOn = "取消隐藏", hideOff = "隐藏",
		place = "放置",
		count = "%d 个", countSel = "%d 个 / 已选 %d 个", noSelection = "未选择", multiSel = "已选择 %d 个",
		folderLabel = "文件夹：%s", mixed = "（混合）", none = "无",
		srcLocal = "本地", srcWorkshop = "创意工坊",
		creativeOnly = "Blueprint Lib 仅限创造模式",
		noIndex = "还没有蓝图列表。请启动 Blueprint Lib Manager 并点击「重新扫描」",
		indexLoaded = "已载入 %d 个蓝图",
		loadFailed = "无法载入蓝图", previewFailed = "无法生成预览（可能缺少 MOD）",
		placed = "已放置：%s", placeFailed = "放置失败：%s",
		hintPlace = "放置", hintRotate = "旋转", hintHeight = "高度 %sm", hintCancel = "取消", hintOpen = "打开蓝图库",
		needFolder = "请先在左侧选择一个自建文件夹", folderExists = "已存在同名文件夹",
		badName = "文件夹名无效（空层级 / 以 * 或 # 开头 / 过长）", badTag = "标签无效",
		folderDeleted = "已删除文件夹（其中的蓝图恢复为未分类）", folderRenamed = "文件夹已改名为「%s」",
		folderCreated = "已创建文件夹「%s」", folderDeletedUp = "已删除文件夹（其中的蓝图已移至「%s」）",
		cantMoveIntoSelf = "不能把文件夹移动到它自身内部",
		modeDynamic = "物理", modeStatic = "固定（静态）", hintMode = "物理/固定",
		placeSeq = "依次放置 (%d)", remotePlace = "来自浏览器：%s 已进入放置模式",
		externalChange = "蓝图库已在浏览器中更改并重新载入（刚才的操作未生效）", queueDone = "已放置所有选中的蓝图",
		placedFrozen = "已放置：%s  ※ %d/%d 个刚体处于固定状态",
		missingFolder = "无法放置（缺少 MOD）", missingShort = "[缺少MOD]",
		missingMods = "缺少 MOD：%s", skipMissing = "%d 个因缺少 MOD 将被跳过（%s）",
		placeDisabled = "缺少 MOD，无法放置", cantPlace = "%s 无法放置（缺少 MOD：%s）",
		nothingSelected = "请先选择蓝图",
		dropped = "已将 %d 个放入「%s」", dropUnfiled = "已将 %d 个移出文件夹",
		dropFav = "已收藏 %d 个", dropHidden = "已隐藏 %d 个", dropShown = "已取消隐藏 %d 个",
		dropTag = "已为 %d 个添加标签「%s」", dropInvalid = "不能放到这里",
		tagAdded = "已为 %d 个添加标签「%s」", tagRemoved = "已从 %d 个中移除标签「%s」",
		selectedAll = "已选择 %d 个"
	}
}
-- A key missing in a translation falls back to English instead of breaking string.format.
-- (Copied in, not via a metatable: the game's Lua sandbox has no setmetatable.)
for lang, tbl in pairs( Texts ) do
	if lang ~= "English" then
		for k, v in pairs( Texts.English ) do
			if tbl[k] == nil then tbl[k] = v end
		end
	end
end

-- Unknown sound names must never break the tool.
local function play( name )
	pcall( sm.audio.play, name )
end

local function T()
	local lang = sm.gui.getCurrentLanguage and sm.gui.getCurrentLanguage() or "English"
	return Texts[lang] or Texts.English
end

-- MyGUI treats "#RRGGBB" as a colour code; "##" prints a literal "#".
local function esc( s )
	return ( tostring( s or "" ):gsub( "#", "##" ) )
end

-- Blueprint names may carry the game's own colour codes ("#ff0000Red"); keep those working
-- like the lift does, but escape any other "#".
local function escName( s )
	s = tostring( s or "" ):gsub( "#", "##" )
	return ( s:gsub( "##(%x%x%x%x%x%x)", "#%1" ) )
end

local function stripColors( s )
	return ( tostring( s or "" ):gsub( "#%x%x%x%x%x%x", "" ) )
end

local function trim( s )
	s = tostring( s or "" ):gsub( "\227\128\128", " " ) -- full-width space
	return ( s:gsub( "^%s+", "" ):gsub( "%s+$", "" ) )
end

local function isUuid( s )
	return type( s ) == "string" and #s == 36 and s:match( "^[%x%-]+$" ) ~= nil
end

local function contentPath( id )
	return "$CONTENT_" .. id
end

local function iconPath( bp )
	return bp.hasIcon ~= false and ( contentPath( bp.id ) .. "/icon.png" ) or EMPTY_IMAGE
end

local function safeFileExists( path )
	local ok, exists = pcall( sm.json.fileExists, path )
	return ok and exists == true
end

local function safeJsonOpen( path )
	if not safeFileExists( path ) then return nil end
	local ok, data = pcall( sm.json.open, path )
	if ok and type( data ) == "table" then return data end
	return nil
end

local function cleanTag( s )
	local tag = trim( s ):gsub( "\239\188\131", "#" ):gsub( "^#+", "" ):gsub( "%s+", "_" )
	return tag
end

----------------------------------------------------------------------------------------------------
-- Blueprint helpers (shared by client preview and server spawn so both line up)
----------------------------------------------------------------------------------------------------

-- Shift the blueprint so its origin sits at the bottom-centre of its (approximate) bounding box.
-- Parts without "bounds" are treated as 1x1x1, so very large parts may be off by a block or two.
local function normalizeBlueprint( bp )
	local minV, maxV
	for _, body in ipairs( bp.bodies or {} ) do
		for _, child in ipairs( body.childs or {} ) do
			if child.pos then
				local a = sm.vec3.new( child.pos.x, child.pos.y, child.pos.z )
				local r = rotateBounds( child.bounds or { x = 1, y = 1, z = 1 }, child.xaxis or 1, child.zaxis or 3 )
				local c = a + r
				local lo, hi = a:min( c ), a:max( c )
				minV = minV and minV:min( lo ) or lo
				maxV = maxV and maxV:max( hi ) or hi
			end
		end
	end
	if not minV then return end

	local off = sm.vec3.new( math.floor( ( minV.x + maxV.x ) * 0.5 ), math.floor( ( minV.y + maxV.y ) * 0.5 ), minV.z )
	for _, body in ipairs( bp.bodies ) do
		for _, child in ipairs( body.childs or {} ) do
			if child.pos then
				child.pos.x, child.pos.y, child.pos.z = child.pos.x - off.x, child.pos.y - off.y, child.pos.z - off.z
			end
		end
	end
	for _, joint in ipairs( bp.joints or {} ) do
		if joint.posA then
			joint.posA.x, joint.posA.y, joint.posA.z = joint.posA.x - off.x, joint.posA.y - off.y, joint.posA.z - off.z
		end
		if joint.posB and joint.childB ~= -1 then
			joint.posB.x, joint.posB.y, joint.posB.z = joint.posB.x - off.x, joint.posB.y - off.y, joint.posB.z - off.z
		end
	end
end

-- Body "type": 0 = dynamic, 1 = static (see Survival/LocalBlueprints). Blueprints saved from the lift
-- omit it; the lift's native importer treats that as dynamic, but sm.creation.importFromString
-- leaves such bodies frozen in place. Always write it explicitly.
local BODY_DYNAMIC, BODY_STATIC = 0, 1

local function setBodyType( bp, static )
	for _, body in ipairs( bp.bodies or {} ) do
		body.type = static and BODY_STATIC or BODY_DYNAMIC
	end
end

local function loadBlueprint( id )
	if not isUuid( id ) then return nil end
	local bp = safeJsonOpen( contentPath( id ) .. "/blueprint.json" )
	if not bp or type( bp.bodies ) ~= "table" then return nil end
	normalizeBlueprint( bp )
	setBodyType( bp, false )
	return bp
end

----------------------------------------------------------------------------------------------------
-- Shape availability: can this blueprint be spawned with the mods loaded in this world?
----------------------------------------------------------------------------------------------------

local VANILLA_PROBE = "df953d9c-234f-4ac2-af5e-f0490b223e71" -- Wood Block Level 1
local shapeCache = {}
local availabilityApi = nil -- nil = not probed yet, false = API unusable (never block anything)

local function probeApi( fn, u )
	if not fn then return false end
	local ok, r = pcall( fn, u )
	return ok and r == true
end

local function rawShapeExists( uuidStr )
	if not ( sm.uuid and sm.uuid.new ) then return false end
	local okU, u = pcall( sm.uuid.new, uuidStr )
	if not okU or not u then return false end
	return probeApi( sm.shape and sm.shape.uuidExists, u )
		or probeApi( sm.item and sm.item.isBlock, u )
		or probeApi( sm.item and sm.item.isPart, u )
		or probeApi( sm.item and sm.item.isJoint, u )
end

-- true when the shape uuid exists in the current game (vanilla or a loaded mod)
local function shapeExists( uuidStr )
	if availabilityApi == nil then
		-- if even a vanilla wood block reads as missing the API can't be trusted: don't block anything
		availabilityApi = rawShapeExists( VANILLA_PROBE )
		if not availabilityApi then
			print( "[BlueprintLib] shape availability check disabled (API did not recognise a vanilla block)" )
		end
	end
	if not availabilityApi then return true end
	uuidStr = tostring( uuidStr ):lower()
	local c = shapeCache[uuidStr]
	if c == nil then
		c = rawShapeExists( uuidStr )
		shapeCache[uuidStr] = c
	end
	return c
end

-- Full check of a loaded blueprint table. Returns the names of missing mods ({} = spawnable).
local function missingModsInBlueprint( bp )
	local owner = {}
	for _, dep in ipairs( type( bp.dependencies ) == "table" and bp.dependencies or {} ) do
		for _, s in ipairs( type( dep.shapeIds ) == "table" and dep.shapeIds or {} ) do
			owner[tostring( s ):lower()] = tostring( dep.name or "?" )
		end
	end
	local missing, seenName, checked = {}, {}, {}
	local function test( id )
		if type( id ) ~= "string" then return end
		id = id:lower()
		if checked[id] then return end
		checked[id] = true
		if not shapeExists( id ) then
			local name = owner[id] or "?"
			if not seenName[name] then
				seenName[name] = true
				missing[#missing + 1] = name
			end
		end
	end
	for _, body in ipairs( bp.bodies or {} ) do
		for _, child in ipairs( body.childs or {} ) do test( child.shapeId ) end
	end
	for _, joint in ipairs( bp.joints or {} ) do test( joint.shapeId ) end
	return missing
end

----------------------------------------------------------------------------------------------------
-- SERVER
----------------------------------------------------------------------------------------------------

function BlueprintLib.sv_place( self, params, player )
	local function reply( ok, reason, extra )
		local res = extra or {}
		res.ok, res.reason, res.id = ok, reason, type( params ) == "table" and params.id or nil
		self.network:sendToClient( player, "cl_onPlaceResult", res )
	end

	if sm.game.getLimitedInventory() then
		reply( false, "creative" )
		return
	end
	if type( params ) ~= "table" or not isUuid( params.id ) then
		reply( false, "params" )
		return
	end
	local posType = type( params.pos )
	if posType ~= "Vec3" and posType ~= "userdata" then
		reply( false, "params" )
		return
	end

	-- Single player / host only: the file has to exist on the host machine.
	local bp = loadBlueprint( params.id )
	if not bp then
		reply( false, "load" )
		return
	end

	-- never hand the engine a blueprint whose parts don't exist in this world
	local missing = missingModsInBlueprint( bp )
	if #missing > 0 then
		reply( false, "missing", { mods = missing } )
		return
	end

	local wantStatic = params.static == true
	setBodyType( bp, wantStatic )

	local world = ( player.character and player.character:getWorld() ) or sm.world.getCurrentWorld()
	local rot = Rotations[params.rot] or Rotations[1]
	local ok, bodies = pcall( sm.creation.importFromString, world, sm.json.writeJsonString( bp ), params.pos, rot )
	if not ok then
		print( "[BlueprintLib] import failed:", bodies )
		reply( false, "import" )
		return
	end

	-- Report how many bodies ended up static so a wrong physics state is visible in game.
	local staticCount, total = 0, 0
	for _, body in ipairs( type( bodies ) == "table" and bodies or {} ) do
		total = total + 1
		if body.isStatic and body:isStatic() then staticCount = staticCount + 1 end
	end
	reply( true, nil, { static = wantStatic, staticCount = staticCount, bodyCount = total } )
end

----------------------------------------------------------------------------------------------------
-- CLIENT: lifecycle & animation (pattern from the game's own tools)
----------------------------------------------------------------------------------------------------

function BlueprintLib.client_onCreate( self )
	self:cl_init()
	self:cl_loadAnimations()
end

function BlueprintLib.client_onRefresh( self )
	self:cl_cancelPlacement()
	self:cl_destroyGui()
	self:cl_init()
	self:cl_loadAnimations()
end

function BlueprintLib.client_onDestroy( self )
	self:cl_cancelPlacement()
	self:cl_destroyGui()
end

function BlueprintLib.cl_destroyGui( self )
	if self.cl and self.cl.gui then
		self.cl.gui:close()
		self.cl.gui:destroy()
		self.cl.gui = nil
	end
end

function BlueprintLib.cl_init( self )
	self.cl = {
		gui = nil,
		index = {}, byId = {}, indexLoaded = false,
		lib = nil,
		filtered = {},
		scope = S_ALL,          -- "*xxx" virtual folder, "#tag" tag filter, otherwise a user folder name
		leftTab = "folders",
		leftEntries = {},
		leftPage = 1,
		page = 1,
		search = "",
		folderInput = "",
		tagInput = "",
		sel = {}, selCount = 0, -- set of selected ids
		focusId = nil,          -- last clicked (shown in the detail panel)
		selectMode = false,
		dropMode = false,
		chipTags = {},
		lastClickId = nil, lastClickTick = 0,
		placing = nil,
		rotationIndex = 1,
		heightIndex = 1,
		forceHeld = false,
		placeStatic = false     -- R toggles fixed placement while placing
	}
end

function BlueprintLib.cl_loadAnimations( self )
	self.tpAnimations = createTpAnimations( self.tool, {
		idle = { "weldtool_idle" },
		use = { "weldtool_use_idle", { nextAnimation = "idle" } },
		pickup = { "weldtool_pickup", { nextAnimation = "idle" } },
		putdown = { "weldtool_putdown" }
	} )
	local movementAnimations = {
		idle = "weldtool_idle", idleRelaxed = "weldtool_idle_relaxed",
		runFwd = "weldtool_run_fwd", runBwd = "weldtool_run_bwd", sprint = "weldtool_sprint",
		jump = "weldtool_jump_start", jumpUp = "weldtool_jump_up", jumpDown = "weldtool_jump_down",
		land = "weldtool_jump_land", landFwd = "weldtool_jump_land_fwd", landBwd = "weldtool_jump_land_bwd",
		crouchIdle = "weldtool_crouch_idle", crouchFwd = "weldtool_crouch_fwd", crouchBwd = "weldtool_crouch_bwd"
	}
	for name, animation in pairs( movementAnimations ) do
		self.tool:setMovementAnimation( name, animation )
	end
	if self.tool:isLocal() then
		self.fpAnimations = createFpAnimations( self.tool, {
			idle = { "weldtool_idle", { looping = true } },
			use = { "weldtool_use_into", { nextAnimation = "idle" } },
			equip = { "weldtool_pickup", { nextAnimation = "idle" } },
			unequip = { "weldtool_putdown" }
		} )
	end
	setTpAnimation( self.tpAnimations, "idle", 5.0 )
	self.blendTime = 0.2
end

function BlueprintLib.client_onUpdate( self, dt )
	if self.tool:isLocal() and self.fpAnimations then
		updateFpAnimations( self.fpAnimations, self.equipped, dt )
	end

	if not self.equipped then
		if self.wantEquipped then
			self.wantEquipped = false
			self.equipped = true
		end
		return
	end

	if self.tool:isLocal() then
		self:cl_pollRequest()
	end

	local crouchWeight = self.tool:isCrouching() and 1.0 or 0.0
	local normalWeight = 1.0 - crouchWeight
	local totalWeight = 0.0
	for name, animation in pairs( self.tpAnimations.animations ) do
		animation.time = animation.time + dt
		if name == self.tpAnimations.currentAnimation then
			animation.weight = math.min( animation.weight + ( self.tpAnimations.blendSpeed * dt ), 1.0 )
			if animation.looping == true and animation.time >= animation.info.duration then
				animation.time = animation.time - animation.info.duration
			end
			if animation.time >= animation.info.duration - self.blendTime and not animation.looping then
				if name == "use" then
					setTpAnimation( self.tpAnimations, "idle", 10.0 )
				elseif name == "pickup" then
					setTpAnimation( self.tpAnimations, "idle", 0.001 )
				elseif animation.nextAnimation ~= "" then
					setTpAnimation( self.tpAnimations, animation.nextAnimation, 0.001 )
				end
			end
		else
			animation.weight = math.max( animation.weight - ( self.tpAnimations.blendSpeed * dt ), 0.0 )
		end
		totalWeight = totalWeight + animation.weight
	end
	totalWeight = totalWeight == 0 and 1.0 or totalWeight
	for name, animation in pairs( self.tpAnimations.animations ) do
		local weight = animation.weight / totalWeight
		if name == "idle" then
			self.tool:updateMovementAnimation( animation.time, weight )
		elseif animation.crouch then
			self.tool:updateAnimation( animation.info.name, animation.time, weight * normalWeight )
			self.tool:updateAnimation( animation.crouch.name, animation.time, weight * crouchWeight )
		else
			self.tool:updateAnimation( animation.info.name, animation.time, weight )
		end
	end
end

function BlueprintLib.client_onEquip( self )
	play( "PotatoRifle - Equip" )
	self.wantEquipped = true
	if self.cl then self.cl.lastNonce = nil end

	local tp, fp = {}, {}
	for _, v in ipairs( renderablesTp ) do tp[#tp + 1] = v end
	for _, v in ipairs( renderablesFp ) do fp[#fp + 1] = v end
	for _, v in ipairs( renderables ) do tp[#tp + 1] = v; fp[#fp + 1] = v end
	self.tool:setTpRenderables( tp )
	if self.tool:isLocal() then
		self.tool:setFpRenderables( fp )
	end

	self:cl_loadAnimations()
	setTpAnimation( self.tpAnimations, "pickup", 0.0001 )
	if self.tool:isLocal() then
		swapFpAnimation( self.fpAnimations, "unequip", "equip", 0.2 )
	end
end

function BlueprintLib.client_onUnequip( self )
	play( "PotatoRifle - Unequip" )
	self.wantEquipped = false
	self.equipped = false
	if sm.exists( self.tool ) then
		setTpAnimation( self.tpAnimations, "putdown" )
		if self.tool:isLocal() and self.fpAnimations and self.fpAnimations.currentAnimation ~= "unequip" then
			swapFpAnimation( self.fpAnimations, "equip", "unequip", 0.2 )
		end
	end
	self:cl_cancelPlacement()
end

----------------------------------------------------------------------------------------------------
-- CLIENT: input
----------------------------------------------------------------------------------------------------

local function isPlaceable( raycastResult )
	if not raycastResult.valid then return false end
	local t = raycastResult.type
	return t ~= "character" and t ~= "lift" and t ~= "limiter"
end

-- sm.gui.setInteractionText accepts at most 5 arguments ("Expected at most 5 arguments (got 11)"
-- spammed the game log every frame). Extra key hints must be concatenated into one string.
-- Only the given (non-nil) arguments are passed on; anything past the 5th is impossible by signature.
-- (No select("#", ...) - keep to the functions the game's Lua sandbox is known to have.)
local function interactionText( a, b, c, d, e )
	local f = sm.gui.setInteractionText
	if e ~= nil then f( a, b, c, d, e )
	elseif d ~= nil then f( a, b, c, d )
	elseif c ~= nil then f( a, b, c )
	elseif b ~= nil then f( a, b )
	else f( a or "" ) end
end

local function key( action )
	return sm.gui.getKeyBinding( action, true )
end

local function fmtHeight( h )
	return ( string.format( "%.2f", h ):gsub( "0+$", "" ):gsub( "%.$", "" ) )
end

function BlueprintLib.client_onEquippedUpdate( self, primaryState, secondaryState, forceBuild )
	if not self.tool:isLocal() then
		return false, false
	end
	local text = T()

	if self.cl.placing then
		-- F (Force Build) cycles the spawn height
		if forceBuild and not self.cl.forceHeld then
			self.cl.heightIndex = self.cl.heightIndex % #HEIGHTS + 1
			play( "ConnectTool - Rotate" )
		end
		self.cl.forceHeld = forceBuild == true

		local preview = self.cl.placing.preview
		local hit, result = sm.localPlayer.getRaycast( PLACE_RANGE )
		local pos = nil
		if hit and isPlaceable( result ) then
			local p = result.pointWorld * 4
			pos = sm.vec3.new( math.floor( p.x + 0.5 ), math.floor( p.y + 0.5 ), math.floor( p.z + 0.5 ) ) * 0.25
				+ sm.vec3.new( 0, 0, HEIGHTS[self.cl.heightIndex] )
			preview:setPosition( pos )
			preview:setRotation( Rotations[self.cl.rotationIndex] )
			preview:setScale( sm.vec3.one() )
		else
			preview:setScale( sm.vec3.zero() ) -- hide
		end

		if primaryState == sm.tool.interactState.start and pos then
			self.network:sendToServer( "sv_place", { id = self.cl.placing.id, pos = pos, rot = self.cl.rotationIndex, static = self.cl.placeStatic } )
			if self.fpAnimations then
				setFpAnimation( self.fpAnimations, "use", 0.25 )
			end
		end
		if secondaryState == sm.tool.interactState.start then
			self:cl_cancelPlacement()
			play( "Blueprint - Close" )
			return true, true
		end

		local q = self.cl.placing.queue
		local title = escName( self.cl.placing.name ) .. "#ffffff"
		if q and #q > 1 then title = title .. string.format( "  (%d/%d)", self.cl.placing.queuePos, #q ) end
		interactionText( title .. "   " .. ( self.cl.placeStatic and text.modeStatic or text.modeDynamic ) )
		interactionText( "", key( "Create" ), text.hintPlace .. "    ", key( "NextCreateRotation" ), text.hintRotate )
		interactionText( "", key( "ForceBuild" ), string.format( text.hintHeight, fmtHeight( HEIGHTS[self.cl.heightIndex] ) ) .. "    ",
			key( "Reload" ), text.hintMode .. "    " .. key( "Attack" ) .. " " .. text.hintCancel )
	else
		self.cl.forceHeld = forceBuild == true
		if secondaryState == sm.tool.interactState.start then
			self:cl_openGui()
		end
		interactionText( "", key( "Attack" ), text.hintOpen )
	end

	return true, true
end

function BlueprintLib.client_onToggle( self, backwards )
	if self.cl.placing then
		local i = self.cl.rotationIndex + ( backwards and -1 or 1 )
		if i > 4 then i = 1 elseif i < 1 then i = 4 end
		self.cl.rotationIndex = i
		play( "GUI Shape rotate" )
	end
	return true
end

-- R: while placing toggles physics / fixed placement, otherwise opens the library.
function BlueprintLib.client_onReload( self )
	if self.cl.placing then
		self.cl.placeStatic = not self.cl.placeStatic
		play( "ConnectTool - Rotate" )
		sm.gui.displayAlertText( self.cl.placeStatic and T().modeStatic or T().modeDynamic, 1.5 )
	else
		self:cl_openGui()
	end
	return true
end

----------------------------------------------------------------------------------------------------
-- CLIENT: placement
----------------------------------------------------------------------------------------------------

-- queue (optional): list of ids placed one after another; each successful placement advances it.
function BlueprintLib.cl_startPlacement( self, id, queue, queuePos )
	local text = T()
	if sm.game.getLimitedInventory() then
		sm.gui.displayAlertText( text.creativeOnly )
		return false
	end
	local entry = self.cl.byId[id]
	local bp = loadBlueprint( id )
	if not bp then
		sm.gui.displayAlertText( text.loadFailed .. ": " .. escName( entry and entry.name or id ) )
		return false
	end
	-- full check against the actual file (the index may be stale)
	local missing = missingModsInBlueprint( bp )
	if #missing > 0 then
		if entry then
			entry.missing, entry.availChecked = missing, true
		end
		sm.gui.displayAlertText( string.format( text.cantPlace, escName( entry and entry.name or id ), esc( table.concat( missing, ", " ) ) ), 4 )
		return false
	end

	self:cl_cancelPlacement()
	local ok, preview = pcall( sm.visualization.createBlueprint, bp )
	if not ok or not preview then
		print( "[BlueprintLib] createBlueprint failed:", preview )
		sm.gui.displayAlertText( text.previewFailed )
		return false
	end
	preview:setScale( sm.vec3.zero() )
	self.cl.placing = { id = id, name = entry and entry.name or id, preview = preview, queue = queue, queuePos = queuePos or 1 }

	if self.cl.gui then
		self.cl.gui:close()
	end
	play( "Blueprint - Open" )
	return true
end

-- move to the next blueprint of a sequential placement; skips entries that fail to load
function BlueprintLib.cl_advanceQueue( self )
	local placing = self.cl.placing
	local queue = placing and placing.queue
	if not queue or #queue <= 1 then return end
	local pos = placing.queuePos
	while pos < #queue do
		pos = pos + 1
		if self:cl_startPlacement( queue[pos], queue, pos ) then return end
	end
	self:cl_cancelPlacement()
	sm.gui.displayAlertText( T().queueDone, 2 )
end

function BlueprintLib.cl_cancelPlacement( self )
	if self.cl and self.cl.placing then
		if self.cl.placing.preview then
			self.cl.placing.preview:destroy()
		end
		self.cl.placing = nil
	end
end

function BlueprintLib.cl_onPlaceResult( self, res )
	local text = T()
	local entry = res.id and self.cl.byId[res.id]
	local name = escName( entry and entry.name or res.id or "?" )
	if res.ok then
		play( "Blueprint - Build" )
		if not res.static and ( res.staticCount or 0 ) > 0 then
			-- diagnostic: physics was requested but the engine still froze some bodies
			sm.gui.displayAlertText( string.format( text.placedFrozen, name, res.staticCount, res.bodyCount or 0 ), 5 )
			print( "[BlueprintLib] static bodies after dynamic import:", res.staticCount, "/", res.bodyCount )
		else
			sm.gui.displayAlertText( string.format( text.placed, name ), 2 )
		end
		self:cl_markUsed( res.id )
		if self.cl.placing and self.cl.placing.id == res.id then
			self:cl_advanceQueue()
		end
	elseif res.reason == "creative" then
		sm.gui.displayAlertText( text.creativeOnly )
	elseif res.reason == "missing" then
		local mods = type( res.mods ) == "table" and res.mods or {}
		if entry then
			entry.missing, entry.availChecked = mods, true
		end
		sm.gui.displayAlertText( string.format( text.cantPlace, name, esc( table.concat( mods, ", " ) ) ), 4 )
		-- a sequential placement just moves on to the next blueprint
		if self.cl.placing and self.cl.placing.id == res.id then
			if self.cl.placing.queue and #self.cl.placing.queue > 1 then
				self:cl_advanceQueue()
			else
				self:cl_cancelPlacement()
			end
		end
	else
		sm.gui.displayAlertText( string.format( text.placeFailed, res.reason or "?" ) )
	end
end

----------------------------------------------------------------------------------------------------
-- CLIENT: data (index = what exists, library = how the user organised it)
----------------------------------------------------------------------------------------------------

function BlueprintLib.cl_loadIndex( self )
	local data = safeJsonOpen( INDEX_PATH )
	self.cl.index, self.cl.byId = {}, {}
	if data and type( data.blueprints ) == "table" then
		for _, bp in ipairs( data.blueprints ) do
			if type( bp ) == "table" and isUuid( bp.id ) then
				bp.name = tostring( bp.name or bp.id )
				bp.lname = stripColors( bp.name ):lower()
				bp.mtime = tonumber( bp.mtime ) or 0
				self.cl.index[#self.cl.index + 1] = bp
				self.cl.byId[bp.id] = bp
			end
		end
		self.cl.indexLoaded = true
	else
		self.cl.indexLoaded = false
	end
	-- drop selections that no longer exist
	for id in pairs( self.cl.sel ) do
		if not self.cl.byId[id] then self.cl.sel[id] = nil end
	end
	self:cl_countSel()
	if self.cl.focusId and not self.cl.byId[self.cl.focusId] then self.cl.focusId = nil end
end

local function hasTag( meta, ltag )
	if meta then
		for _, t in ipairs( meta.tags ) do
			if t:lower() == ltag then return true end
		end
	end
	return false
end

local function folderIndex( lib, name )
	for i, f in ipairs( lib.folders ) do
		if f == name then return i end
	end
	return nil
end

-- Folder hierarchy: folders are stored as full paths, "Tanks/Heavy/Prototypes".
local function isUnder( path, ancestor ) -- true for the folder itself and every descendant
	return path == ancestor or path:sub( 1, #ancestor + 1 ) == ancestor .. "/"
end

local function parentOf( path )
	return path:match( "^(.*)/[^/]*$" )
end

local function leafOf( path )
	return path:match( "([^/]*)$" )
end

local function depthOf( path )
	local _, n = path:gsub( "/", "" )
	return n
end

local function folderSortKey( path )
	return ( path:lower():gsub( "/", "\1" ) ) -- keep children directly below their parent
end

local function sortFolders( lib )
	table.sort( lib.folders, function( a, b ) return folderSortKey( a ) < folderSortKey( b ) end )
end

-- Normalise a typed path ("a / b", full-width "／" allowed). nil when any segment is empty or reserved.
local function cleanPath( s )
	s = tostring( s or "" ):gsub( "\239\188\143", "/" )
	local segs = {}
	for seg in ( s .. "/" ):gmatch( "([^/]*)/" ) do
		seg = trim( seg )
		local c = seg:sub( 1, 1 )
		if seg == "" or c == "*" or c == "#" then return nil end
		segs[#segs + 1] = seg
	end
	local path = table.concat( segs, "/" )
	if #segs == 0 or #path > MAX_NAME_BYTES then return nil end
	return path
end

local function ensureFolder( lib, path ) -- adds the folder and any missing ancestors
	local p = path
	while p and p ~= "" do
		if not folderIndex( lib, p ) then table.insert( lib.folders, p ) end
		p = parentOf( p )
	end
end

local function folderHasChildren( lib, path )
	for _, f in ipairs( lib.folders ) do
		if f ~= path and isUnder( f, path ) then return true end
	end
	return false
end

-- sm.json.save turns empty tables into null, so normalise everything on load.
function BlueprintLib.cl_loadLibrary( self )
	local lib = safeJsonOpen( LIBRARY_PATH ) or {}
	if type( lib.folders ) ~= "table" then lib.folders = {} end
	if type( lib.items ) ~= "table" then lib.items = {} end
	if type( lib.settings ) ~= "table" then lib.settings = {} end
	for id, meta in pairs( lib.items ) do
		if type( meta ) ~= "table" then
			lib.items[id] = nil
		elseif type( meta.tags ) ~= "table" then
			meta.tags = {}
		end
	end
	if type( lib.collapsed ) ~= "table" then lib.collapsed = {} end
	-- make the folder tree consistent (older versions stored flat names; items may point at
	-- folders that were never listed)
	local folders = lib.folders
	lib.folders = {}
	for _, f in ipairs( folders ) do
		local path = type( f ) == "string" and cleanPath( f ) or nil
		if path then ensureFolder( lib, path ) end
	end
	for _, meta in pairs( lib.items ) do
		-- a folder name starting with "*" or "#" would be mistaken for a virtual scope / tag
		local path = type( meta.folder ) == "string" and cleanPath( meta.folder ) or nil
		meta.folder = path
		if path then ensureFolder( lib, path ) end
	end
	sortFolders( lib )
	lib.useCounter = tonumber( lib.useCounter ) or 0
	lib.version = 3
	lib.rev = tonumber( lib.rev ) or 0 -- bumped on every save by the game and by the web manager
	self.cl.lib = lib

	local s = lib.settings
	self.cl.view = VIEWS[s.view] and s.view or "G"
	self.cl.sortIndex = 1
	for i, name in ipairs( SORTS ) do
		if name == s.sort then self.cl.sortIndex = i end
	end
end

local function diskRev()
	local disk = safeJsonOpen( LIBRARY_PATH )
	return disk and tonumber( disk.rev ) or 0
end

-- Called at the start of every in-game edit: if the web manager saved since we loaded the
-- library, take its version first, so the edit is applied on top of it instead of being lost.
function BlueprintLib.cl_syncLibrary( self )
	if not self.cl.lib then
		self:cl_loadLibrary()
		return true
	end
	if diskRev() > self.cl.lib.rev then
		self:cl_loadLibrary()
		return true
	end
	return false
end

-- Optimistic concurrency with the web manager. Edits call cl_syncLibrary first, so a conflict here
-- only happens if the browser saved in the last few milliseconds; then the file wins and we reload.
function BlueprintLib.cl_saveLibrary( self )
	if diskRev() > self.cl.lib.rev then
		self:cl_loadLibrary()
		sm.gui.displayAlertText( T().externalChange, 4 )
		if self.cl.gui then self:cl_refresh() end
		return false
	end
	self.cl.lib.settings = { view = self.cl.view, sort = SORTS[self.cl.sortIndex] }
	local oldRev = self.cl.lib.rev
	self.cl.lib.rev = oldRev + 1
	local ok, err = pcall( sm.json.save, self.cl.lib, LIBRARY_PATH )
	if not ok then
		self.cl.lib.rev = oldRev -- the file still has the old revision
		print( "[BlueprintLib] could not save library:", err )
	end
	return ok
end

-- "Place in game" from the web manager: it writes Data/request.json { id, nonce }.
-- Polled once a second while the tool is held; requests older than the equip are ignored.
function BlueprintLib.cl_pollRequest( self )
	local tick = sm.game.getCurrentTick()
	if tick - ( self.cl.lastPollTick or 0 ) < REQUEST_POLL_TICKS then return end
	self.cl.lastPollTick = tick
	local req = safeJsonOpen( REQUEST_PATH )
	local nonce = req and tostring( req.nonce or "" ) or ""
	if self.cl.lastNonce == nil then
		self.cl.lastNonce = nonce -- baseline at equip time
		return
	end
	if nonce == "" or nonce == self.cl.lastNonce then return end
	self.cl.lastNonce = nonce
	if not isUuid( req.id ) then return end
	if not self.cl.indexLoaded then self:cl_loadIndex() end
	if not self.cl.lib then self:cl_loadLibrary() end
	if self.cl.gui then self.cl.gui:close() end
	if self:cl_startPlacement( req.id ) then
		sm.gui.displayAlertText( string.format( T().remotePlace, escName( self.cl.placing.name ) ), 2 )
	end
end

function BlueprintLib.cl_meta( self, id, create )
	local meta = self.cl.lib.items[id]
	if not meta and create then
		meta = { tags = {} }
		self.cl.lib.items[id] = meta
	end
	return meta
end

function BlueprintLib.cl_pruneMeta( self, id )
	local meta = self.cl.lib.items[id]
	if meta and ( not meta.folder or meta.folder == "" ) and not meta.fav and not meta.hidden
		and not meta.used and #meta.tags == 0 then
		self.cl.lib.items[id] = nil
	end
end

function BlueprintLib.cl_markUsed( self, id )
	if not ( id and self.cl.lib ) then return end
	self:cl_syncLibrary()
	self.cl.lib.useCounter = self.cl.lib.useCounter + 1
	self:cl_meta( id, true ).used = self.cl.lib.useCounter
	self:cl_saveLibrary()
end


local function splitTerms( s )
	local terms = {}
	for word in trim( s ):lower():gsub( "\239\188\131", "#" ):gmatch( "%S+" ) do
		if word:sub( 1, 1 ) == "#" then
			if #word > 1 then terms[#terms + 1] = { tag = word:sub( 2 ) } end
		else
			terms[#terms + 1] = { text = word }
		end
	end
	return terms
end

local function matches( bp, meta, terms )
	for _, term in ipairs( terms ) do
		local found = false
		if term.text and bp.lname:find( term.text, 1, true ) then
			found = true
		end
		if not found and term.text and meta and meta.folder and meta.folder:lower():find( term.text, 1, true ) then
			found = true
		end
		if not found and meta then
			for _, tag in ipairs( meta.tags ) do
				if tag:lower():find( term.tag or term.text, 1, true ) then
					found = true
					break
				end
			end
		end
		if not found then return false end
	end
	return true
end

local Sorters = {
	new = function( a, b ) if a.mtime ~= b.mtime then return a.mtime > b.mtime end return a.id < b.id end,
	old = function( a, b ) if a.mtime ~= b.mtime then return a.mtime < b.mtime end return a.id < b.id end,
	name = function( a, b ) if a.lname ~= b.lname then return a.lname < b.lname end return a.id < b.id end
}

function BlueprintLib.cl_inScope( self, bp, meta )
	local scope = self.cl.scope
	local hidden = meta ~= nil and meta.hidden == true
	if scope == S_HIDDEN then return hidden end
	if hidden then return false end
	if scope == S_ALL then return true end
	if scope == S_FAV then return meta ~= nil and meta.fav == true end
	if scope == S_RECENT then return meta ~= nil and meta.used ~= nil end
	if scope == S_UNFILED then return not ( meta and meta.folder and meta.folder ~= "" ) end
	if scope == S_WORKSHOP then return bp.source == "workshop" end
	if scope == S_MISSING then return not self:cl_isPlaceable( bp ) end
	if scope:sub( 1, 1 ) == "#" then return hasTag( meta, scope:sub( 2 ) ) end
	-- a folder shows its own blueprints and everything in its subfolders
	return meta ~= nil and meta.folder ~= nil and isUnder( meta.folder, scope )
end

function BlueprintLib.cl_scopeExists( self )
	local scope = self.cl.scope
	local c = scope:sub( 1, 1 )
	if c == "*" then return true end
	if c == "#" then
		local ltag = scope:sub( 2 )
		for _, meta in pairs( self.cl.lib.items ) do
			if hasTag( meta, ltag ) then return true end
		end
		return false
	end
	return folderIndex( self.cl.lib, scope ) ~= nil
end

function BlueprintLib.cl_applyFilter( self )
	if not self:cl_scopeExists() then
		self.cl.scope = S_ALL
		self.cl.page = 1
	end
	local terms = splitTerms( self.cl.search )
	local items = self.cl.lib.items
	local out = {}
	for _, bp in ipairs( self.cl.index ) do
		local meta = items[bp.id]
		if self:cl_inScope( bp, meta ) and matches( bp, meta, terms ) then
			bp.used = meta and meta.used or 0
			out[#out + 1] = bp
		end
	end

	local sortName = SORTS[self.cl.sortIndex]
	if self.cl.scope == S_RECENT or sortName == "used" then
		table.sort( out, function( a, b )
			if a.used ~= b.used then return a.used > b.used end
			return Sorters.new( a, b )
		end )
		if self.cl.scope == S_RECENT then
			for i = #out, RECENT_LIMIT + 1, -1 do out[i] = nil end
		end
	else
		table.sort( out, Sorters[sortName] )
	end

	self.cl.filtered = out
	local size = VIEWS[self.cl.view].size
	local pages = math.max( 1, math.ceil( #out / size ) )
	self.cl.page = math.min( math.max( self.cl.page, 1 ), pages )
end

-- selection helpers ------------------------------------------------------------------------------

-- Quick availability from the index (non-vanilla shapes per mod). Returns missing mod names.
-- Cached on the index entry; the authoritative check runs again on the real file when placing.
function BlueprintLib.cl_missingMods( self, bp )
	if bp.availChecked then return bp.missing end
	bp.availChecked = true
	local missing = {}
	for _, mod in ipairs( type( bp.mods ) == "table" and bp.mods or {} ) do
		for _, u in ipairs( type( mod.shapes ) == "table" and mod.shapes or {} ) do
			if not shapeExists( u ) then
				missing[#missing + 1] = tostring( mod.name or "?" )
				break
			end
		end
	end
	bp.missing = missing
	return missing
end

function BlueprintLib.cl_isPlaceable( self, bp )
	return #self:cl_missingMods( bp ) == 0
end

function BlueprintLib.cl_countSel( self )
	local n = 0
	for _ in pairs( self.cl.sel ) do n = n + 1 end
	self.cl.selCount = n
end

function BlueprintLib.cl_selIds( self )
	local ids = {}
	for _, bp in ipairs( self.cl.index ) do -- index order keeps results stable
		if self.cl.sel[bp.id] then ids[#ids + 1] = bp.id end
	end
	return ids
end

function BlueprintLib.cl_requireSel( self )
	if self.cl.selCount == 0 then
		sm.gui.displayAlertText( T().nothingSelected )
		return nil
	end
	return self:cl_selIds()
end

-- apply fn(meta, id) to every selected blueprint, then prune & save
function BlueprintLib.cl_bulk( self, fn )
	local ids = self:cl_requireSel()
	if not ids then return 0 end
	self:cl_syncLibrary()
	for _, id in ipairs( ids ) do
		fn( self:cl_meta( id, true ), id )
		self:cl_pruneMeta( id )
	end
	self:cl_saveLibrary()
	return #ids
end

----------------------------------------------------------------------------------------------------
-- CLIENT: GUI
----------------------------------------------------------------------------------------------------

function BlueprintLib.cl_createGui( self )
	local gui = sm.gui.createGuiFromLayout( LAYOUT_PATH, false, {
		isHud = false,
		isInteractive = true,
		needsCursor = true,
		hidesHotbar = false,
		isOverlapped = false,
		backgroundAlpha = 0.5
	} )
	for i = 0, FOLDER_ROWS - 1 do gui:setButtonCallback( "Folder" .. i, "cl_onLeftClick" ) end
	for p, view in pairs( VIEWS ) do
		for i = 0, view.size - 1 do gui:setButtonCallback( p .. "Item" .. i, "cl_onItemClick" ) end
		gui:setButtonCallback( "View" .. p, "cl_onViewButton" )
	end
	for i = 0, CHIP_COUNT - 1 do gui:setButtonCallback( "Chip" .. i, "cl_onChipClick" ) end
	-- layout files can't expand $CONTENT_DATA, so (re)assign the overlay images from script
	for p, view in pairs( VIEWS ) do
		for i = 0, view.size - 1 do
			gui:setImage( p .. "Check" .. i, CHECK_IMAGE )
			gui:setImage( p .. "Warn" .. i, WARN_IMAGE )
		end
	end
	local buttons = {
		TabFolders = "cl_onLeftTab", TabTags = "cl_onLeftTab",
		FolderPrev = "cl_onLeftPage", FolderNext = "cl_onLeftPage",
		GridPrev = "cl_onGridPage", GridNext = "cl_onGridPage",
		CreateFolder = "cl_onCreateFolder", RenameFolder = "cl_onRenameFolder", DeleteFolder = "cl_onDeleteFolder",
		Reload = "cl_onReloadIndex", Sort = "cl_onSort",
		SelectMode = "cl_onSelectMode", SelectAll = "cl_onSelectAll", SelectNone = "cl_onSelectNone",
		AddTag = "cl_onAddTag", DropMode = "cl_onDropMode",
		Unfile = "cl_onUnfile", Favorite = "cl_onFavorite", Hide = "cl_onHide", Place = "cl_onPlaceButton"
	}
	for widget, cb in pairs( buttons ) do gui:setButtonCallback( widget, cb ) end
	gui:setTextChangedCallback( "Search", "cl_onSearchChanged" )
	gui:setTextChangedCallback( "FolderInput", "cl_onFolderInputChanged" )
	gui:setTextChangedCallback( "TagInput", "cl_onTagInputChanged" )

	local text = T()
	local captions = {
		TabFolders = text.tabFolders, TabTags = text.tabTags,
		CreateFolder = text.create, RenameFolder = text.rename, DeleteFolder = text.delete, Reload = text.reload,
		ViewL = text.viewL, ViewG = text.viewG, ViewR = text.viewR,
		SelectMode = text.selectMode, SelectAll = text.selectAll, SelectNone = text.selectNone,
		TagHeader = text.tagHeader, AddTag = text.addTag, Unfile = text.unfile, Place = text.place
	}
	for widget, caption in pairs( captions ) do gui:setText( widget, caption ) end
	self.cl.gui = gui
end

function BlueprintLib.cl_openGui( self )
	if sm.game.getLimitedInventory() then
		sm.gui.displayAlertText( T().creativeOnly )
		return
	end
	if not self.cl.gui then
		self:cl_createGui()
	end
	if not self.cl.indexLoaded then
		self:cl_loadIndex()
		if not self.cl.indexLoaded then
			sm.gui.displayAlertText( T().noIndex, 5 )
		end
		self:cl_logAvailability()
	end
	-- re-read on every open so edits made outside the game (or by another tool) show up
	self:cl_loadLibrary()
	self:cl_refresh()
	self.cl.gui:open()
end

-- one line in the game log (Logs/game-*.log) to diagnose the missing-mod detection
function BlueprintLib.cl_logAvailability( self )
	local withMods, blocked, sample = 0, 0, nil
	for _, bp in ipairs( self.cl.index ) do
		if type( bp.mods ) == "table" and #bp.mods > 0 then withMods = withMods + 1 end
		local missing = self:cl_missingMods( bp )
		if #missing > 0 then
			blocked = blocked + 1
			sample = sample or ( bp.name .. " <- " .. table.concat( missing, ", " ) )
		end
	end
	print( string.format( "[BlueprintLib] index=%d withModParts=%d blocked=%d api=%s uuidExists=%s sample=%s",
		#self.cl.index, withMods, blocked, tostring( availabilityApi ),
		tostring( sm.shape ~= nil and sm.shape.uuidExists ~= nil ), tostring( sample ) ) )
end

function BlueprintLib.cl_refresh( self )
	self:cl_applyFilter()
	self:cl_renderLeft()
	self:cl_renderToolbar()
	self:cl_renderItems()
	self:cl_renderDetail()
end

-- left panel: folders tab / tags tab ---------------------------------------------------------------

function BlueprintLib.cl_buildLeftEntries( self )
	local text, lib = T(), self.cl.lib
	local entries = {}

	if self.cl.leftTab == "tags" then
		local counts, display = {}, {}
		for _, bp in ipairs( self.cl.index ) do
			local meta = lib.items[bp.id]
			if meta and not meta.hidden then
				for _, t in ipairs( meta.tags ) do
					local k = t:lower()
					counts[k] = ( counts[k] or 0 ) + 1
					display[k] = display[k] or t
				end
			end
		end
		local keys = {}
		for k in pairs( counts ) do keys[#keys + 1] = k end
		table.sort( keys )
		for _, k in ipairs( keys ) do
			entries[#entries + 1] = { id = "#" .. k, label = "##" .. esc( display[k] ) .. " (" .. counts[k] .. ")", tag = display[k] }
		end
		return entries
	end

	local n = { all = 0, fav = 0, recent = 0, unfiled = 0, workshop = 0, hidden = 0, missing = 0 }
	local counts = {}
	for _, bp in ipairs( self.cl.index ) do
		local meta = lib.items[bp.id]
		if meta and meta.hidden then
			n.hidden = n.hidden + 1
		else
			n.all = n.all + 1
			if meta and meta.fav then n.fav = n.fav + 1 end
			if meta and meta.used then n.recent = n.recent + 1 end
			if bp.source == "workshop" then n.workshop = n.workshop + 1 end
			if not self:cl_isPlaceable( bp ) then n.missing = n.missing + 1 end
			if meta and meta.folder and meta.folder ~= "" then
				counts[meta.folder] = ( counts[meta.folder] or 0 ) + 1
			else
				n.unfiled = n.unfiled + 1
			end
		end
	end
	local function add( id, label, count ) entries[#entries + 1] = { id = id, label = label .. " (" .. count .. ")" } end
	add( S_ALL, text.all, n.all )
	add( S_FAV, text.fav, n.fav )
	add( S_RECENT, text.recent, math.min( n.recent, RECENT_LIMIT ) )
	add( S_UNFILED, text.unfiled, n.unfiled )
	if n.workshop > 0 then add( S_WORKSHOP, text.workshop, n.workshop ) end
	if n.missing > 0 then add( S_MISSING, text.missingFolder, n.missing ) end
	add( S_HIDDEN, text.hidden, n.hidden )

	-- folder tree: counts include subfolders; children of collapsed folders are skipped
	local total = {}
	for f, c in pairs( counts ) do
		local p = f
		while p do
			total[p] = ( total[p] or 0 ) + c
			p = parentOf( p )
		end
	end
	for _, f in ipairs( lib.folders ) do
		local visible = true
		local p = parentOf( f )
		while p do
			if lib.collapsed[p] then visible = false break end
			p = parentOf( p )
		end
		if visible then
			local marker = ""
			if folderHasChildren( lib, f ) then
				marker = lib.collapsed[f] and "[+] " or "[-] "
			end
			local label = string.rep( "    ", depthOf( f ) ) .. marker .. esc( leafOf( f ) ) .. " (" .. ( total[f] or 0 ) .. ")"
			entries[#entries + 1] = { id = f, label = label, folder = true }
		end
	end
	return entries
end

function BlueprintLib.cl_renderLeft( self )
	local gui, text = self.cl.gui, T()
	local entries = self:cl_buildLeftEntries()
	self.cl.leftEntries = entries

	local pages = math.max( 1, math.ceil( #entries / FOLDER_ROWS ) )
	self.cl.leftPage = math.min( math.max( self.cl.leftPage, 1 ), pages )
	local start = ( self.cl.leftPage - 1 ) * FOLDER_ROWS
	for i = 0, FOLDER_ROWS - 1 do
		local e = entries[start + i + 1]
		gui:setVisible( "Folder" .. i, e ~= nil )
		if e then
			gui:setText( "Folder" .. i, e.label )
			gui:setButtonState( "Folder" .. i, e.id == self.cl.scope )
		end
	end
	gui:setText( "FolderPage", self.cl.leftPage .. "/" .. pages )
	gui:setVisible( "FolderPrev", self.cl.leftPage > 1 )
	gui:setVisible( "FolderNext", self.cl.leftPage < pages )
	gui:setButtonState( "TabFolders", self.cl.leftTab == "folders" )
	gui:setButtonState( "TabTags", self.cl.leftTab == "tags" )
	-- the tree only shows leaf names, so spell out where we are (and where "Create" will put things)
	local here = ""
	if self.cl.dropMode then
		here = text.dropHint
	elseif self.cl.leftTab == "folders" and folderIndex( self.cl.lib, self.cl.scope ) then
		here = esc( self.cl.scope ) .. "/"
	end
	gui:setText( "DropHint", here )

	local isUserFolder = self.cl.scope:sub( 1, 1 ) ~= "*" and self.cl.scope:sub( 1, 1 ) ~= "#"
	local folderTools = self.cl.leftTab == "folders"
	gui:setVisible( "FolderInputBg", folderTools )
	gui:setVisible( "CreateFolder", folderTools )
	gui:setVisible( "RenameFolder", folderTools and isUserFolder )
	gui:setVisible( "DeleteFolder", folderTools and isUserFolder )
end

function BlueprintLib.cl_renderToolbar( self )
	local gui, text = self.cl.gui, T()
	for p, view in pairs( VIEWS ) do
		gui:setVisible( view.panel, p == self.cl.view )
		gui:setButtonState( "View" .. p, p == self.cl.view )
	end
	gui:setText( "Sort", text.sort[SORTS[self.cl.sortIndex]] )
	gui:setButtonState( "SelectMode", self.cl.selectMode )
end

function BlueprintLib.cl_itemInfo( self, bp )
	local meta = self.cl.lib.items[bp.id]
	local parts = {}
	if meta and meta.fav then parts[#parts + 1] = "*" end
	if meta and meta.folder then parts[#parts + 1] = "[" .. meta.folder .. "]" end
	if meta then
		for _, t in ipairs( meta.tags ) do parts[#parts + 1] = "#" .. t end
	end
	if bp.source == "workshop" then parts[#parts + 1] = "(Workshop)" end
	local missing = self:cl_missingMods( bp )
	if #missing > 0 then
		return "#ff6060" .. T().missingShort .. " #8b999f" .. esc( table.concat( parts, " " ) )
	end
	return esc( table.concat( parts, " " ) )
end

function BlueprintLib.cl_renderItems( self )
	local gui, text = self.cl.gui, T()
	local p = self.cl.view
	local view = VIEWS[p]
	local list = self.cl.filtered
	local pages = math.max( 1, math.ceil( #list / view.size ) )
	local start = ( self.cl.page - 1 ) * view.size
	for i = 0, view.size - 1 do
		local bp = list[start + i + 1]
		gui:setVisible( p .. "Item" .. i, bp ~= nil )
		if bp then
			local selected = self.cl.sel[bp.id] == true
			gui:setImage( p .. "Icon" .. i, iconPath( bp ) )
			gui:setText( p .. "Name" .. i, escName( bp.name ) )
			gui:setButtonState( p .. "Item" .. i, selected )
			gui:setVisible( p .. "Check" .. i, selected and ( self.cl.selectMode or self.cl.selCount > 1 ) )
			gui:setVisible( p .. "Warn" .. i, not self:cl_isPlaceable( bp ) )
			if view.list then
				gui:setText( p .. "Info" .. i, self:cl_itemInfo( bp ) )
			end
		end
	end
	gui:setText( "GridPage", self.cl.page .. "/" .. pages )
	gui:setVisible( "GridPrev", self.cl.page > 1 )
	gui:setVisible( "GridNext", self.cl.page < pages )
	if self.cl.selCount > 0 then
		gui:setText( "Status", string.format( text.countSel, #list, self.cl.selCount ) )
	else
		gui:setText( "Status", string.format( text.count, #list ) )
	end
end

function BlueprintLib.cl_renderDetail( self )
	local gui, text = self.cl.gui, T()
	local ids = self:cl_selIds()
	local n = #ids
	local controls = { "TagHeader", "TagInputBg", "AddTag", "DropMode", "Unfile", "Favorite", "Hide" }
	for _, name in ipairs( controls ) do gui:setVisible( name, n > 0 ) end

	local focus = self.cl.focusId and self.cl.sel[self.cl.focusId] and self.cl.byId[self.cl.focusId]
	if not focus and n > 0 then focus = self.cl.byId[ids[1]] end

	if n == 0 then
		gui:setImage( "DetailIcon", EMPTY_IMAGE )
		gui:setText( "DetailName", text.noSelection )
		gui:setText( "DetailInfo", "" )
		gui:setText( "DetailFolder", "" )
		gui:setVisible( "Place", false )
		gui:setVisible( "PlaceDisabled", false )
		gui:setText( "DetailWarn", "" )
		for i = 0, CHIP_COUNT - 1 do gui:setVisible( "Chip" .. i, false ) end
		self.cl.chipTags = {}
		return
	end

	-- aggregate over the selection
	local items = self.cl.lib.items
	local folder, folderMixed = nil, false
	local allFav, allHidden = true, true
	local tagCount, tagDisplay, tagOrder = {}, {}, {}
	for idx, id in ipairs( ids ) do
		local meta = items[id]
		local f = meta and meta.folder or nil
		if idx == 1 then folder = f elseif f ~= folder then folderMixed = true end
		if not ( meta and meta.fav ) then allFav = false end
		if not ( meta and meta.hidden ) then allHidden = false end
		if meta then
			for _, t in ipairs( meta.tags ) do
				local k = t:lower()
				if not tagCount[k] then
					tagOrder[#tagOrder + 1] = k
					tagDisplay[k] = t
				end
				tagCount[k] = ( tagCount[k] or 0 ) + 1
			end
		end
	end

	gui:setImage( "DetailIcon", iconPath( focus ) )
	if n == 1 then
		gui:setText( "DetailName", escName( focus.name ) )
		gui:setText( "DetailInfo", ( focus.source == "workshop" and text.srcWorkshop or text.srcLocal ) .. "  " .. focus.id:sub( 1, 8 ) )
	else
		gui:setText( "DetailName", string.format( text.multiSel, n ) )
		gui:setText( "DetailInfo", escName( focus.name ) )
	end
	local folderText = folderMixed and text.mixed or ( folder and esc( folder ) or text.none )
	gui:setText( "DetailFolder", string.format( text.folderLabel, folderText ) )

	self.cl.chipTags = {}
	for i = 0, CHIP_COUNT - 1 do
		local k = tagOrder[i + 1]
		gui:setVisible( "Chip" .. i, k ~= nil )
		if k then
			self.cl.chipTags[i] = tagDisplay[k]
			local label = "##" .. esc( tagDisplay[k] )
			if n > 1 then label = label .. " " .. tagCount[k] .. "/" .. n end
			gui:setText( "Chip" .. i, label .. "  x" )
		end
	end

	gui:setText( "Favorite", allFav and text.favOn or text.favOff )
	gui:setText( "Hide", allHidden and text.hideOn or text.hideOff )
	gui:setText( "DropMode", self.cl.dropMode and text.dropModeOn or text.dropMode )
	gui:setButtonState( "DropMode", self.cl.dropMode )
	-- placement availability: disable when nothing selected can be spawned, warn about the rest
	local blocked, blockedMods, seenMod = 0, {}, {}
	for _, id in ipairs( ids ) do
		local missing = self:cl_missingMods( self.cl.byId[id] )
		if #missing > 0 then
			blocked = blocked + 1
			for _, m in ipairs( missing ) do
				if not seenMod[m] then
					seenMod[m] = true
					blockedMods[#blockedMods + 1] = m
				end
			end
		end
	end
	local placeable = n - blocked
	local modList = esc( table.concat( blockedMods, ", " ) )
	if blocked == 0 then
		gui:setText( "DetailWarn", "" )
	elseif n == 1 then
		gui:setText( "DetailWarn", "#ff6060" .. string.format( text.missingMods, modList ) )
	else
		gui:setText( "DetailWarn", "#ff6060" .. string.format( text.skipMissing, blocked, modList ) )
	end
	gui:setVisible( "Place", placeable > 0 )
	gui:setVisible( "PlaceDisabled", placeable == 0 )
	gui:setText( "PlaceDisabled", text.placeDisabled )
	gui:setText( "Place", n > 1 and string.format( text.placeSeq, placeable ) or text.place )
end

-- GUI callbacks: navigation ------------------------------------------------------------------------

function BlueprintLib.cl_onLeftTab( self, button )
	self.cl.leftTab = button == "TabTags" and "tags" or "folders"
	self.cl.leftPage = 1
	self:cl_renderLeft()
end

function BlueprintLib.cl_onLeftPage( self, button )
	self.cl.leftPage = self.cl.leftPage + ( button == "FolderNext" and 1 or -1 )
	self:cl_renderLeft()
end

function BlueprintLib.cl_onLeftClick( self, button )
	local idx = tonumber( button:sub( 7 ) )
	local e = idx and self.cl.leftEntries[( self.cl.leftPage - 1 ) * FOLDER_ROWS + idx + 1]
	if not e then return end
	if self.cl.dropMode then
		self:cl_dropInto( e )
		return
	end
	-- clicking the already selected folder folds / unfolds its subfolders
	if e.folder and e.id == self.cl.scope and folderHasChildren( self.cl.lib, e.id ) then
		local collapse = not self.cl.lib.collapsed[e.id]
		self:cl_syncLibrary()
		self.cl.lib.collapsed[e.id] = collapse or nil
		self:cl_saveLibrary()
		self:cl_renderLeft()
		return
	end
	self.cl.scope = e.id
	self.cl.page = 1
	self:cl_refresh()
end

function BlueprintLib.cl_onViewButton( self, button )
	self:cl_syncLibrary()
	local p = button:sub( 5 )
	if not VIEWS[p] or p == self.cl.view then
		self:cl_renderToolbar()
		return
	end
	-- keep the first visible item on screen when switching views
	local first = ( self.cl.page - 1 ) * VIEWS[self.cl.view].size
	self.cl.view = p
	self.cl.page = math.floor( first / VIEWS[p].size ) + 1
	self:cl_saveLibrary()
	self:cl_applyFilter()
	self:cl_renderToolbar()
	self:cl_renderItems()
end

function BlueprintLib.cl_onSort( self )
	self:cl_syncLibrary()
	self.cl.sortIndex = self.cl.sortIndex % #SORTS + 1
	self.cl.page = 1
	self:cl_saveLibrary()
	self:cl_applyFilter()
	self:cl_renderToolbar()
	self:cl_renderItems()
end

function BlueprintLib.cl_onGridPage( self, button )
	self.cl.page = self.cl.page + ( button == "GridNext" and 1 or -1 )
	self:cl_applyFilter()
	self:cl_renderItems()
end

function BlueprintLib.cl_onSearchChanged( self, widget, value )
	self.cl.search = value or ""
	self.cl.page = 1
	self:cl_applyFilter()
	self:cl_renderItems()
end

function BlueprintLib.cl_onFolderInputChanged( self, widget, value )
	self.cl.folderInput = value or ""
end

function BlueprintLib.cl_onTagInputChanged( self, widget, value )
	self.cl.tagInput = value or ""
end

function BlueprintLib.cl_onReloadIndex( self )
	self:cl_loadIndex()
	self:cl_loadLibrary()
	sm.gui.displayAlertText( self.cl.indexLoaded and string.format( T().indexLoaded, #self.cl.index ) or T().noIndex, 3 )
	self:cl_refresh()
end

-- GUI callbacks: selection ------------------------------------------------------------------------

function BlueprintLib.cl_onItemClick( self, button )
	local p, idx = button:match( "^(%a)Item(%d+)$" )
	local view = p and VIEWS[p]
	local bp = view and self.cl.filtered[( self.cl.page - 1 ) * view.size + tonumber( idx ) + 1]
	if not bp then return end

	local tick = sm.game.getCurrentTick()
	local isDouble = self.cl.lastClickId == bp.id and ( tick - self.cl.lastClickTick ) <= DOUBLE_CLICK_TICKS
	self.cl.lastClickId, self.cl.lastClickTick = bp.id, tick

	if self.cl.selectMode then
		if self.cl.sel[bp.id] then
			self.cl.sel[bp.id] = nil
			if self.cl.focusId == bp.id then self.cl.focusId = nil end
		else
			self.cl.sel[bp.id] = true
			self.cl.focusId = bp.id
		end
	else
		self.cl.sel = { [bp.id] = true }
		self.cl.focusId = bp.id
		if isDouble then
			self:cl_countSel()
			self:cl_startPlacement( bp.id )
			return
		end
	end
	self:cl_countSel()
	if self.cl.selCount == 0 and self.cl.dropMode then
		self.cl.dropMode = false
		self:cl_renderLeft()
	end
	self:cl_renderItems()
	self:cl_renderDetail()
end

function BlueprintLib.cl_onSelectMode( self )
	self.cl.selectMode = not self.cl.selectMode
	self:cl_renderToolbar()
	self:cl_renderItems()
end

function BlueprintLib.cl_onSelectAll( self )
	for _, bp in ipairs( self.cl.filtered ) do self.cl.sel[bp.id] = true end
	self.cl.selectMode = true
	self:cl_countSel()
	sm.gui.displayAlertText( string.format( T().selectedAll, self.cl.selCount ), 2 )
	self:cl_renderToolbar()
	self:cl_renderItems()
	self:cl_renderDetail()
end

function BlueprintLib.cl_onSelectNone( self )
	self.cl.sel = {}
	self.cl.focusId = nil
	self.cl.dropMode = false
	self:cl_countSel()
	self:cl_refresh()
end

-- GUI callbacks: bulk edits -----------------------------------------------------------------------

function BlueprintLib.cl_onDropMode( self )
	if not self.cl.dropMode and self.cl.selCount == 0 then
		sm.gui.displayAlertText( T().nothingSelected )
		return
	end
	self.cl.dropMode = not self.cl.dropMode
	-- the drop targets live on the left; make sure a useful tab is showing
	self:cl_renderLeft()
	self:cl_renderDetail()
end

-- "drag & drop" substitute: put the selection into the clicked left-panel entry
function BlueprintLib.cl_dropInto( self, e )
	local text = T()
	if self.cl.selCount == 0 then
		-- nothing left to drop (selection emptied meanwhile): behave like a normal click
		self.cl.dropMode = false
		self.cl.scope = e.id
		self.cl.page = 1
		self:cl_refresh()
		return
	end
	local msg
	local id = e.id
	if id == S_RECENT or id == S_WORKSHOP or id == S_MISSING then
		sm.gui.displayAlertText( text.dropInvalid )
		return
	elseif id == S_UNFILED then
		msg = string.format( text.dropUnfiled, self:cl_bulk( function( m ) m.folder = nil end ) )
	elseif id == S_FAV then
		msg = string.format( text.dropFav, self:cl_bulk( function( m ) m.fav = true end ) )
	elseif id == S_HIDDEN then
		msg = string.format( text.dropHidden, self:cl_bulk( function( m ) m.hidden = true end ) )
	elseif id == S_ALL then
		msg = string.format( text.dropShown, self:cl_bulk( function( m ) m.hidden = nil end ) )
	elseif id:sub( 1, 1 ) == "#" then
		local tag = e.tag
		msg = string.format( text.dropTag, self:cl_bulk( function( m )
			if not hasTag( m, tag:lower() ) then table.insert( m.tags, tag ) end
		end ), esc( tag ) )
	else
		msg = string.format( text.dropped, self:cl_bulk( function( m ) m.folder = id end ), esc( id ) )
		ensureFolder( self.cl.lib, id ) -- the folder may have been removed in the browser meanwhile
	end
	self.cl.dropMode = false
	play( "Blueprint - Build" )
	sm.gui.displayAlertText( msg, 2 )
	self:cl_refresh()
end

function BlueprintLib.cl_onAddTag( self )
	local tag = cleanTag( self.cl.tagInput )
	if tag == "" or #tag > MAX_TAG_BYTES then
		sm.gui.displayAlertText( T().badTag )
		return
	end
	local n = self:cl_bulk( function( m )
		if not hasTag( m, tag:lower() ) then table.insert( m.tags, tag ) end
	end )
	if n == 0 then return end
	sm.gui.displayAlertText( string.format( T().tagAdded, n, esc( tag ) ), 2 )
	self.cl.tagInput = ""
	self.cl.gui:setText( "TagInput", "" )
	self:cl_refresh()
end

function BlueprintLib.cl_onChipClick( self, button )
	local tag = self.cl.chipTags[tonumber( button:sub( 5 ) )]
	if not tag then return end
	local ltag = tag:lower()
	local n = self:cl_bulk( function( m )
		for i = #m.tags, 1, -1 do
			if m.tags[i]:lower() == ltag then table.remove( m.tags, i ) end
		end
	end )
	sm.gui.displayAlertText( string.format( T().tagRemoved, n, esc( tag ) ), 2 )
	self:cl_refresh()
end

function BlueprintLib.cl_onUnfile( self )
	if self:cl_bulk( function( m ) m.folder = nil end ) > 0 then self:cl_refresh() end
end

function BlueprintLib.cl_onFavorite( self )
	self:cl_syncLibrary()
	local ids = self:cl_selIds()
	local allFav = #ids > 0
	for _, id in ipairs( ids ) do
		local m = self.cl.lib.items[id]
		if not ( m and m.fav ) then allFav = false break end
	end
	if self:cl_bulk( function( m ) m.fav = ( not allFav ) or nil end ) > 0 then self:cl_refresh() end
end

function BlueprintLib.cl_onHide( self )
	self:cl_syncLibrary()
	local ids = self:cl_selIds()
	local allHidden = #ids > 0
	for _, id in ipairs( ids ) do
		local m = self.cl.lib.items[id]
		if not ( m and m.hidden ) then allHidden = false break end
	end
	if self:cl_bulk( function( m ) m.hidden = ( not allHidden ) or nil end ) > 0 then self:cl_refresh() end
end

function BlueprintLib.cl_onPlaceButton( self )
	local n = self.cl.selCount
	if n == 0 then return end
	if n == 1 then
		self:cl_startPlacement( self:cl_selIds()[1] )
		return
	end
	-- several selected: place them one after another, in the order currently shown
	local queue, seen = {}, {}
	for _, bp in ipairs( self.cl.filtered ) do
		if self.cl.sel[bp.id] then
			if self:cl_isPlaceable( bp ) then queue[#queue + 1] = bp.id end
			seen[bp.id] = true
		end
	end
	for _, id in ipairs( self:cl_selIds() ) do
		local bp = self.cl.byId[id]
		if not seen[id] and bp and self:cl_isPlaceable( bp ) then queue[#queue + 1] = id end
	end
	if #queue == 0 then
		sm.gui.displayAlertText( T().placeDisabled )
		return
	end
	local pos = 1
	while pos <= #queue do
		if self:cl_startPlacement( queue[pos], queue, pos ) then return end
		pos = pos + 1
	end
end

-- GUI callbacks: folders ---------------------------------------------------------------------------
-- Folder input rules:  "Name" = inside the selected folder (or top level),  "A/B" = nested path
-- relative to the selected folder,  "/A/B" = absolute path from the top level.

function BlueprintLib.cl_currentFolder( self )
	local scope = self.cl.scope
	if folderIndex( self.cl.lib, scope ) then return scope end
	return nil
end

function BlueprintLib.cl_clearFolderInput( self )
	self.cl.folderInput = ""
	self.cl.gui:setText( "FolderInput", "" )
end

function BlueprintLib.cl_onCreateFolder( self )
	self:cl_syncLibrary()
	local raw = trim( self.cl.folderInput ):gsub( "\239\188\143", "/" )
	local absolute = raw:sub( 1, 1 ) == "/"
	local rel = cleanPath( absolute and raw:sub( 2 ) or raw )
	if not rel then
		sm.gui.displayAlertText( T().badName )
		return
	end
	local parent = ( not absolute ) and self:cl_currentFolder() or nil
	local path = parent and ( parent .. "/" .. rel ) or rel
	if #path > MAX_NAME_BYTES then
		sm.gui.displayAlertText( T().badName )
		return
	end
	if folderIndex( self.cl.lib, path ) then
		sm.gui.displayAlertText( T().folderExists )
		return
	end
	ensureFolder( self.cl.lib, path )
	sortFolders( self.cl.lib )
	if parent then self.cl.lib.collapsed[parent] = nil end -- show the new child
	self:cl_saveLibrary()
	self:cl_clearFolderInput()
	sm.gui.displayAlertText( string.format( T().folderCreated, esc( path ) ), 2 )
	-- in drop mode the new folder is an immediate drop target; otherwise open it
	if not self.cl.dropMode then
		self.cl.scope = path
		self.cl.page = 1
	end
	self:cl_refresh()
end

-- Renames the selected folder; typing a path containing "/" moves it (with its subfolders).
function BlueprintLib.cl_onRenameFolder( self )
	self:cl_syncLibrary()
	local old = self:cl_currentFolder()
	if not old then
		sm.gui.displayAlertText( T().needFolder )
		return
	end
	local raw = trim( self.cl.folderInput ):gsub( "\239\188\143", "/" )
	local new
	if raw:sub( 1, 1 ) == "/" then
		new = cleanPath( raw:sub( 2 ) )                 -- absolute from the top level
	else
		local rel = cleanPath( raw )                     -- relative to where the folder is now
		local parent = parentOf( old )
		new = rel and ( parent and ( parent .. "/" .. rel ) or rel )
	end
	if not new or #new > MAX_NAME_BYTES then
		sm.gui.displayAlertText( T().badName )
		return
	end
	if new == old then return end
	if isUnder( new, old ) then
		sm.gui.displayAlertText( T().cantMoveIntoSelf )
		return
	end
	if folderIndex( self.cl.lib, new ) then
		sm.gui.displayAlertText( T().folderExists )
		return
	end

	local lib = self.cl.lib
	local function remap( path )
		if path and isUnder( path, old ) then return new .. path:sub( #old + 1 ) end
		return path
	end
	local folders = lib.folders
	lib.folders = {}
	for _, f in ipairs( folders ) do ensureFolder( lib, remap( f ) ) end
	sortFolders( lib )
	for _, meta in pairs( lib.items ) do meta.folder = remap( meta.folder ) end
	local collapsed = {}
	for f, v in pairs( lib.collapsed ) do collapsed[remap( f )] = v end
	lib.collapsed = collapsed

	self:cl_saveLibrary()
	self:cl_clearFolderInput()
	self.cl.scope = new
	sm.gui.displayAlertText( string.format( T().folderRenamed, esc( new ) ), 2 )
	self:cl_refresh()
end

-- Deletes the selected folder and its subfolders; their blueprints move up to the parent folder.
function BlueprintLib.cl_onDeleteFolder( self )
	self:cl_syncLibrary()
	local name = self:cl_currentFolder()
	if not name then return end
	local lib = self.cl.lib
	local parent = parentOf( name )
	for i = #lib.folders, 1, -1 do
		if isUnder( lib.folders[i], name ) then table.remove( lib.folders, i ) end
	end
	for id, meta in pairs( lib.items ) do
		if meta.folder and isUnder( meta.folder, name ) then
			meta.folder = parent
			self:cl_pruneMeta( id )
		end
	end
	for f in pairs( lib.collapsed ) do
		if isUnder( f, name ) then lib.collapsed[f] = nil end
	end
	self:cl_saveLibrary()
	self.cl.scope = parent or S_ALL
	sm.gui.displayAlertText( parent and string.format( T().folderDeletedUp, esc( parent ) ) or T().folderDeleted, 3 )
	self:cl_refresh()
end
