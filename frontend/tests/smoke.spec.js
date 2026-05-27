import { test, expect } from '@playwright/test'

async function mockCommonApi(page) {
  await page.route('**/api/config/roles', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        { code: 'WOLF', name: '狼人', camp: '狼人阵营', icon: '🐺' },
        { code: 'SEER', name: '预言家', camp: '好人阵营', icon: '🔮' },
        { code: 'WITCH', name: '女巫', camp: '好人阵营', icon: '🧙‍♀️' },
        { code: 'VILLAGER', name: '村民', camp: '好人阵营', icon: '👨‍🌾' },
      ]),
    })
  })

  await page.route('**/api/config/personalities', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        { code: 'leader_bold', name: '勇敢领袖型', description: '敢于发言、敢带节奏' },
        { code: 'rational_analyst', name: '理性分析型', description: '偏好列举信息和分析票型' },
      ]),
    })
  })

  await page.route('**/api/config/models', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        { id: 'gpt-5.4-mini', label: 'gpt-5.4-mini' },
        { id: 'gpt-5.4', label: 'gpt-5.4' },
      ]),
    })
  })

  await page.route('**/api/config/presets', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: 'standard_6p',
          name: '标准六人局',
          description: '2狼 + 预言家 + 女巫 + 守卫 + 村民',
          total_players: 6,
          num_wolves: 2,
          role_config: { WOLF: 2, SEER: 1, WITCH: 1, GUARD: 1, VILLAGER: 1 },
        },
        {
          id: 'lovers_7p',
          name: '情侣七人局',
          description: '加入丘比特验证情侣链',
          total_players: 7,
          num_wolves: 2,
          role_config: { WOLF: 2, CUPID: 1, SEER: 1, WITCH: 1, GUARD: 1, VILLAGER: 1 },
        },
      ]),
    })
  })

  await page.route('**/api/stats/overview', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        total_games: 12,
        total_rounds: 34,
        wolf_wins: 5,
        good_wins: 7,
        wolf_win_rate: 5 / 12,
        good_win_rate: 7 / 12,
        avg_duration: 420,
      }),
    })
  })
}

test('前端关键页面可正常浏览和操作', async ({ page }) => {
  await mockCommonApi(page)

  await page.route('**/api/stats/roles', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        '狼人': { games: 6, wins: 2, deaths: 4, win_rate: 2 / 6 },
        '预言家': { games: 6, wins: 4, deaths: 2, win_rate: 4 / 6 },
      }),
    })
  })

  await page.route('**/api/stats/personalities', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        '勇敢领袖型': { games: 8, win_rate: 0.5, wolf_win_rate: 0.4, wolf_games: 5, good_win_rate: 0.66, good_games: 3 },
      }),
    })
  })

  await page.route('**/api/stats/models', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        'gpt-5.4-mini': { games: 10, win_rate: 0.6, wolf_win_rate: 0.5, good_win_rate: 0.7 },
      }),
    })
  })

  await page.route('**/api/stats/history?**', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        games: [
          {
            game_id: 'game_20260522_091251_7f8e8c0c',
            start_time: '2026-05-22T09:12:51',
            total_rounds: 2,
            num_humans: 1,
            duration: 128,
            winner_camp: '好人阵营',
          },
        ],
        page: 1,
        pages: 1,
      }),
    })
  })

  await page.route('**/api/admin/check', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ configured: true, message: '管理员密码已配置' }),
    })
  })

  await page.route('**/api/admin/login', async route => {
    const body = route.request().postDataJSON()
    const ok = body.password === 'admin-smoke-pass'
    await route.fulfill({
      status: ok ? 200 : 403,
      contentType: 'application/json',
      body: JSON.stringify(ok ? {
        success: true,
        access_token: 'smoke-token',
        expires_at: '2026-05-23T09:00:00',
      } : { detail: '密码错误' }),
    })
  })

  await page.route('**/api/admin/verify', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ valid: true, admin: 'admin', expires_at: '2026-05-23T09:00:00' }),
    })
  })

  await page.route('**/api/admin/config', async route => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          api_url: 'https://example.com/v1',
          api_key_masked: '***test',
          model_ids: ['gpt-5.4-mini'],
          models: ['gpt-5.4-mini'],
          default_timeout: 60,
          model_timeout_map: { 'gpt-5.4-mini': 60 },
        }),
      })
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, message: '配置已更新' }),
    })
  })

  await page.route('**/api/admin/fetch-models', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        total: 2,
        model_ids: ['gpt-5.4-mini', 'gpt-5.4'],
        models: ['gpt-5.4-mini', 'gpt-5.4'],
      }),
    })
  })

  await page.route('**/api/game/create', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        game_id: 'game_smoke_frontend',
        players: [],
        status: 'waiting',
        god_mode_enabled: false,
      }),
    })
  })

  await page.goto('/')
  await expect(page.getByText('智能 狼人杀')).toBeVisible()
  await expect(page.getByText('总对局数')).toBeVisible()

  await page.getByRole('link', { name: '开始游戏' }).first().click()
  await expect(page).toHaveURL(/\/setup$/)
  await expect(page.getByRole('heading', { name: '游戏设置' })).toBeVisible()
  await expect(page.getByRole('button', { name: /标准六人局/ })).toBeVisible()
  await page.getByRole('button', { name: /情侣七人局/ }).click()
  await page.getByRole('button', { name: '1' }).click()
  await expect(page.getByText('已选择 1 个真人玩家座位')).toBeVisible()

  await page.getByRole('link', { name: '历史记录' }).click()
  await expect(page).toHaveURL(/\/history$/)
  await expect(page.getByRole('heading', { name: '历史记录与统计' })).toBeVisible()
  await page.getByRole('button', { name: /📜 对局历史/ }).click()
  await expect(page.getByText('对局 20260522 091251')).toBeVisible()
  await expect(page.getByText('好人阵营')).toBeVisible()

  await page.goto('/admin')
  await expect(page.getByRole('heading', { name: '管理员登录' })).toBeVisible()
  await page.getByPlaceholder('请输入密码').fill('admin-smoke-pass')
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page.getByRole('heading', { name: '控制面板' })).toBeVisible()
  await page.getByRole('button', { name: '📥 获取模型编号列表' }).click()
  await expect(page.locator('.fixed.bottom-6.right-6')).toContainText('获取到 2 个模型编号')
})
