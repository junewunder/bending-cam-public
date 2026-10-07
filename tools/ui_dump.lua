local spr = app.open(app.params.file)

local tags = {}
for _, t in ipairs(spr.tags) do
  tags[t.name] = t
end

local function hex(s)
  return (s:gsub(".", function(c) return string.format("%02x", c:byte()) end))
end

local function render(f)
  local img = Image(spr.spec)
  img:drawSprite(spr, f)
  local x0, y0, x1, y1 = spr.width, spr.height, -1, -1
  for it in img:pixels() do
    if app.pixelColor.rgbaA(it()) > 0 then
      if it.x < x0 then x0 = it.x end
      if it.y < y0 then y0 = it.y end
      if it.x > x1 then x1 = it.x end
      if it.y > y1 then y1 = it.y end
    end
  end
  if x1 < 0 then
    return { x = 0, y = 0, w = 0, h = 0, rgba = "" }
  end
  local crop = Image(img, Rectangle(x0, y0, x1 - x0 + 1, y1 - y0 + 1))
  return { x = x0, y = y0, w = crop.width, h = crop.height, rgba = hex(crop.bytes) }
end

local top = {}
for _, l in ipairs(spr.layers) do
  top[#top + 1] = l
end

local out = { width = spr.width, height = spr.height, statuses = {}, strays = {} }
for _, slot in ipairs(top) do
  if slot.name:sub(1, 1) == "_" then
  elseif not slot.isGroup then
    out.strays[#out.strays + 1] = slot.name
  else
    for _, st in ipairs(slot.layers) do
      for _, l in ipairs(top) do
        l.isVisible = (l == slot)
      end
      for _, s in ipairs(slot.layers) do
        s.isVisible = (s == st)
      end
      local tag = tags[st.name]
      local first, last = 1, 1
      if tag then
        first, last = tag.fromFrame.frameNumber, tag.toFrame.frameNumber
      end
      local frames = {}
      for f = first, last do
        local r = render(f)
        r.frame = f
        r.ms = math.floor(spr.frames[f].duration * 1000 + 0.5)
        frames[#frames + 1] = r
      end
      out.statuses[#out.statuses + 1] = {
        slot = slot.name,
        name = st.name,
        group = st.isGroup,
        tagged = tag ~= nil,
        dir = tag and tag.aniDir or 0,
        repeats = tag and tag.repeats or 0,
        frames = frames,
      }
    end
  end
end

print(json.encode(out))
