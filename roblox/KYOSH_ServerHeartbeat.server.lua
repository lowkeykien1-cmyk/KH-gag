-- KYOSH authorized heartbeat integration
-- ONLY install this Script in a Roblox experience you own or are authorized to modify.
-- Enable Game Settings > Security > Allow HTTP Requests.
-- Set KYOSH_API_URL and KYOSH_API_KEY below to your own Render endpoint and server-side secret.
-- This reports only the current server's public presence. It does NOT access another game's
-- internals, send mailbox gifts, collect credentials, or expose secrets to clients.

local HttpService = game:GetService("HttpService")
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")

local API_URL = "https://YOUR-RENDER-SERVICE.onrender.com/api/monitor/heartbeat"
local API_KEY = "SET_THIS_IN_SERVER_SCRIPT_ONLY"
local INTERVAL_SECONDS = 30

local function postHeartbeat(player)
    if not player or not player.Parent then
        return
    end

    local payload = {
        user_id = tostring(player.UserId),
        username = player.Name,
        display_name = player.DisplayName,
        place_id = tostring(game.PlaceId),
        server_job_id = game.JobId,
    }

    local ok, response = pcall(function()
        return HttpService:RequestAsync({
            Url = API_URL,
            Method = "POST",
            Headers = {
                ["Content-Type"] = "application/json",
                ["Authorization"] = "Bearer " .. API_KEY,
            },
            Body = HttpService:JSONEncode(payload),
        })
    end)

    if not ok then
        warn("[KYOSH] Heartbeat request failed:", response)
        return
    end
    if not response.Success then
        warn("[KYOSH] Heartbeat rejected:", response.StatusCode)
    end
end

local function startPlayerHeartbeat(player)
    task.spawn(function()
        while player.Parent do
            postHeartbeat(player)
            task.wait(INTERVAL_SECONDS)
        end
    end)
end

Players.PlayerAdded:Connect(startPlayerHeartbeat)
for _, player in ipairs(Players:GetPlayers()) do
    startPlayerHeartbeat(player)
end
