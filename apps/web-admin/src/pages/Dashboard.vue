<script setup lang="ts">
import { ref } from 'vue'

const isHovered = ref<string | null>(null)
const isPressed = ref<string | null>(null)
const activeTab = ref('day')
const isLeftPanelOpen = ref(true)
const isRightPanelOpen = ref(true)
const currentView = ref('dashboard')

// 右侧卡片展开状态
const expandedCard = ref<string | null>(null)

// 日期范围
const showDatePicker = ref(false)
const dateRangeText = ref('自定义日期范围')
const tempStartDate = ref<number | null>(null)
const tempEndDate = ref<number | null>(null)

// Live2D 模型选择
const showModelSelector = ref(false)
const selectedModel = ref('Ayaka_v1')

// 服务建议回复框状态
const replyingTo = ref<number | null>(null)
const replyText = ref('')

const bgUrl = ref('https://images.unsplash.com/photo-1554797589-7241bb691973?q=80&w=1080&h=2340&fit=crop')
const fileInput = ref<HTMLInputElement | null>(null)

function setTab(tab: string) { activeTab.value = tab; dateRangeText.value = '自定义日期范围' }
function toggleBothPanels() {
  if (isLeftPanelOpen.value || isRightPanelOpen.value) { isLeftPanelOpen.value = false; isRightPanelOpen.value = false }
  else { isLeftPanelOpen.value = true; isRightPanelOpen.value = true }
}
function toggleCard(cardId: string) { expandedCard.value = expandedCard.value === cardId ? null : cardId }
function handleBgUpload(e: Event) {
  const t = e.target as HTMLInputElement
  if (t.files?.[0]) {
    const r = new FileReader()
    r.onload = (ev) => { if (ev.target?.result) bgUrl.value = ev.target.result as string }
    r.readAsDataURL(t.files[0]); t.value = ''
    console.log('API: POST /api/v1/backgrounds')
  }
}
function selectMockDate(d: number) {
  if (tempStartDate.value === null) tempStartDate.value = d
  else if (tempEndDate.value === null) { if (d >= tempStartDate.value!) tempEndDate.value = d; else { tempEndDate.value = tempStartDate.value; tempStartDate.value = d } }
  else { tempStartDate.value = d; tempEndDate.value = null }
}
function confirmDateRange() {
  if (tempStartDate.value && tempEndDate.value) dateRangeText.value = `2026.05.${String(tempStartDate.value).padStart(2,'0')} - 05.${String(tempEndDate.value).padStart(2,'0')}`
  else if (tempStartDate.value) dateRangeText.value = `2026.05.${String(tempStartDate.value).padStart(2,'0')}`
  showDatePicker.value = false; activeTab.value = 'custom'
}
function handleReply(idx: number) {
  console.log(`Replying to suggestion ${idx}: ${replyText.value}`)
  replyingTo.value = null
  replyText.value = ''
}
</script>

<template>
  <div class="admin-root">
    <div class="layout-wrapper">
      <img class="fullscreen-bg" :src="bgUrl" alt="BG" />

      <!-- Navbar -->
      <header class="navbar">
        <div class="logo-zone">
          <svg class="logo-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
          <div class="logo-text"><span class="logo-cn">人物形象管理</span><span class="logo-en">Avatar Management System</span></div>
        </div>
        <nav class="nav-menu">
          <button class="nav-item" :class="{active:currentView==='dashboard'}" @click="currentView='dashboard'">数据概览</button>
          <button class="nav-item" :class="{active:currentView==='api'}" @click="currentView='api'">API 配置</button>
          <button class="nav-item">内容管理</button>
          <button class="nav-item" :class="{active:currentView==='settings'}" @click="currentView='settings'">系统设置</button>
        </nav>
        <div class="user-glass">
          <button class="bell-btn"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#6B7280" stroke-width="2"><path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 01-3.46 0"/></svg></button>
          <div class="text-avatar">A</div>
          <span class="username">管理员</span>
        </div>
      </header>

      <!-- ==================== DASHBOARD VIEW ==================== -->
      <main v-if="currentView==='dashboard'" class="main-container">
        <!-- Left peek handle -->
        <div class="peek left-peek" :class="{show:!isLeftPanelOpen}" @click="isLeftPanelOpen=true"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg></div>

        <!-- Left Panel -->
        <aside class="left-panel" :class="{hidden:!isLeftPanelOpen}">
          <div class="panel-hd"><h3>形象库与配置</h3><button class="icon-btn" @click="isLeftPanelOpen=false"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg></button></div>
          <div class="persona-grid">
            <div class="persona-card active">
              <img src="https://upload-os-bbs.hoyolab.com/upload/2021/07/20/38115682/d06d48259ed08781ab16dc32ce52627e_2991054924734893898.png" />
              <div class="card-name">神里绫华 (白鹭)</div>
            </div>
            <div class="persona-card">
              <img src="https://images.unsplash.com/photo-1544005313-94ddf0286df2?q=80&w=260&h=260&fit=crop" />
              <div class="card-name">官方导游 (基础)</div>
            </div>
          </div>
          <div class="setting-tabs"><div class="stab active">外观</div><div class="stab">服装</div><div class="stab">声音</div></div>
          <div class="setting-list">
            <div class="sitem"><span>Live2D 模型</span><span class="sval model-link" @click="showModelSelector=!showModelSelector">{{ selectedModel }}</span></div>
            <!-- Model selector dropdown -->
            <div v-if="showModelSelector" class="model-drop">
              <div v-for="m in ['Ayaka_v1','Hiyori_v3','Eira_Default','Shinobu_v2']" :key="m" class="model-opt" :class="{sel:m===selectedModel}" @click="selectedModel=m;showModelSelector=false">{{ m }}</div>
            </div>
            <div class="sitem"><span>待机动作</span><span class="sval">自然呼吸</span></div>
            <div class="sitem"><span>待机动作（失去网络时）</span><span class="sval">挥手示意</span></div>
            <div class="sitem"><span>默认语速</span><span class="sval">1.0x</span></div>
          </div>
        </aside>

        <!-- Center Panel (Fixed width to prevent shifting) -->
        <section class="center-panel">
          <div class="preview-box">
            <div class="sdk-holder">
              <svg viewBox="0 0 24 24" width="56" height="56" fill="none" stroke="rgba(255,255,255,0.7)" stroke-width="1.2"><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>
              <span class="ph-text">Live2D 渲染区</span>
            </div>
          </div>
          <div class="center-actions">
            <button class="act-pill active" @click="toggleBothPanels">形象预览</button>
            <button class="act-pill">动作设置</button>
            <button class="act-pill">语音测试</button>
            <button class="act-pill">更多设置</button>
          </div>
        </section>

        <!-- Right peek handle -->
        <div class="peek right-peek" :class="{show:!isRightPanelOpen}" @click="isRightPanelOpen=true"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg></div>

        <!-- Right Panel -->
        <aside class="right-panel" :class="{hidden:!isRightPanelOpen}">
          <div class="rp-inner">
            <div class="rp-hd"><button class="icon-btn" @click="isRightPanelOpen=false"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg></button><h2>运营数据概览</h2></div>

            <!-- 日期筛选行 -->
            <div class="date-row">
              <div class="db-tabs">
                <button class="tbtn" :class="{active:activeTab==='day'}" @click="setTab('day')">今日</button>
                <button class="tbtn" :class="{active:activeTab==='week'}" @click="setTab('week')">本周</button>
                <button class="tbtn" :class="{active:activeTab==='month'}" @click="setTab('month')">本月</button>
              </div>
              <div class="date-picker-wrap">
                <button class="dp-btn" :class="{active:activeTab==='custom'}" @click="showDatePicker=!showDatePicker"><span>{{ dateRangeText }}</span> <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg></button>
                <div v-if="showDatePicker" class="cal-drop">
                  <div class="cal-month">2026年 5月</div>
                  <div class="cal-grid"><div class="cal-dow" v-for="d in ['日','一','二','三','四','五','六']" :key="d">{{d}}</div><div class="cal-empty" v-for="i in 5" :key="'e'+i"></div><div v-for="d in 31" :key="d" class="cal-day" :class="{sel:tempStartDate===d||tempEndDate===d,mid:tempStartDate&&tempEndDate&&d>tempStartDate&&d<tempEndDate}" @click="selectMockDate(d)">{{d}}</div></div>
                  <div class="cal-btns"><button @click="showDatePicker=false">取消</button><button class="ok" @click="confirmDateRange">确认</button></div>
                </div>
              </div>
            </div>

            <div class="metric-grid">
              <div class="mcard"><div class="mt">服务人次</div><div class="mv">1,258</div><div class="mtr up"><svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg> 环比＋12.5%</div></div>
              <div class="mcard"><div class="mt">交互对话数</div><div class="mv">8,432</div><div class="mtr up"><svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg> 环比＋5.2%</div></div>
              <div class="mcard"><div class="mt">平均响应延迟</div><div class="mv">1.2s</div><div class="mtr dn"><svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 18 13.5 8.5 8.5 13.5 1 6"/><polyline points="17 18 23 18 23 12"/></svg> 环比＋0.1s</div></div>
              <div class="mcard"><div class="mt">用户满意度</div><div class="mv">98.5%</div><div class="mtr up"><svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg> 环比＋1.0%</div></div>
            </div>

            <!-- 可点击展开卡片行 -->
            <div class="charts2col">
              <!-- TOP5 卡片 -->
              <div class="cchart" @click="toggleCard('top5')"><h3>高频问答 TOP5</h3><div class="top5-list"><div v-for="(q,i) in [{rank:1,text:'洗手间在哪里？',cnt:342},{rank:2,text:'今天有什么表演？',cnt:289},{rank:3,text:'餐厅推荐',cnt:215},{rank:4,text:'怎么去北门？',cnt:198},{rank:5,text:'门票包含哪些项目？',cnt:156}]" :key="i" class="t5row"><span class="t5idx" :class="'r'+q.rank">{{q.rank}}</span><span class="t5txt">{{q.text}}</span><span class="t5cnt">{{q.cnt}}次</span></div></div></div>
              <!-- 满意度折线 -->
              <div class="cchart" @click="toggleCard('trend')"><h3>用户满意度趋势 (%)</h3>
                <svg viewBox="0 0 100 60" preserveAspectRatio="none" style="width:100%;flex:1;overflow:visible">
                  <g stroke="rgba(0,0,0,0.05)" stroke-width=".5"><line x1="15" y1="12" x2="95" y2="12"/><line x1="15" y1="27" x2="95" y2="27"/><line x1="15" y1="42" x2="95" y2="42"/></g>
                  <g fill="#9CA3AF" font-size="4" text-anchor="end"><text x="13" y="13.5">100</text><text x="13" y="28.5">90</text><text x="13" y="43.5">80</text></g>
                  <g fill="#9CA3AF" font-size="4" text-anchor="middle"><text x="25" y="52">05.25</text><text x="45" y="52">05.26</text><text x="65" y="52">05.27</text><text x="85" y="52">05.28</text></g>
                  <defs><linearGradient id="g2" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="rgba(59,130,246,0.25)"/><stop offset="100%" stop-color="rgba(59,130,246,0)"/></linearGradient></defs>
                  <path d="M15,40 L15,15 L35,22 L55,10 L75,18 L95,8 L95,40 Z" fill="url(#g2)"/>
                  <polyline points="15,15 35,22 55,10 75,18 95,8" fill="none" stroke="#3B82F6" stroke-width="1.5" stroke-linecap="round"/>
                  <circle cx="15" cy="15" r="1.5" fill="#FFF" stroke="#3B82F6" stroke-width=".8"/><circle cx="35" cy="22" r="1.5" fill="#FFF" stroke="#3B82F6" stroke-width=".8"/><circle cx="55" cy="10" r="1.5" fill="#FFF" stroke="#3B82F6" stroke-width=".8"/><circle cx="75" cy="18" r="1.5" fill="#FFF" stroke="#3B82F6" stroke-width=".8"/><circle cx="95" cy="8" r="1.5" fill="#FFF" stroke="#3B82F6" stroke-width=".8"/>
                </svg>
              </div>
            </div>

            <div class="charts3col">
              <div class="cchart" @click="toggleCard('cloud')"><h3>游客关注词云</h3><div class="cloud"><span class="cw c1">路线</span><span class="cw c2">美食</span><span class="cw c3">表演时间</span><span class="cw c4">门票</span><span class="cw c5">天气</span><span class="cw c6">洗手间</span><span class="cw c7">停车</span><span class="cw c4">地铁</span><span class="cw c5">优惠</span></div></div>
              <div class="cchart" @click="toggleCard('sentiment')"><h3>情感分析</h3><div class="donut"><svg viewBox="0 0 36 36" width="100%"><path d="M18 2a16 16 0 110 32 16 16 0 010-32" fill="none" stroke="#E5E7EB" stroke-width="4"/><path d="M18 2a16 16 0 110 32" fill="none" stroke="#10B981" stroke-width="4" stroke-dasharray="75,100"/><text x="18" y="20.5" font-size="8" text-anchor="middle" fill="#1F2937" font-weight="700">75%</text></svg></div></div>
              <div class="cchart" @click="toggleCard('feedback')"><h3>最新服务建议</h3><div class="fb-list"><div v-for="(f,i) in [{t:'10:42',txt:'建议增加英文导览语音选项。'},{t:'09:15',txt:'路线规划很准，但希望标识更明显。'},{t:'昨天',txt:'数字人很有趣，孩子很喜欢。'}]" :key="i" class="fbi"><span class="fbt">{{f.t}}</span><span class="fbtxt">{{f.txt}}</span></div></div></div>
            </div>
          </div>
        </aside>

        <!-- 展开卡片覆盖层 -->
        <transition name="fade">
          <div v-if="expandedCard" class="expand-overlay" @click.self="expandedCard=null">
            <div class="expand-card">
              <button class="x-btn" @click="expandedCard=null"><svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
              <!-- TOP5 expanded -->
              <template v-if="expandedCard==='top5'"><h2 style="margin:0 0 24px;color:#1F2937">高频问答 TOP5 · 详细</h2><div style="display:flex;flex-direction:column;gap:14px;font-size:16px"><div v-for="(q,i) in [{r:1,t:'洗手间在哪里？',c:342,p:'32%'},{r:2,t:'今天有什么表演？',c:289,p:'27%'},{r:3,t:'餐厅推荐',c:215,p:'20%'},{r:4,t:'怎么去北门？',c:198,p:'18%'},{r:5,t:'门票包含哪些项目？',c:156,p:'14%'}]" :key="i" style="display:flex;align-items:center;gap:12px"><span :style="{background:q.r===1?'#FEF2F2':q.r===2?'#FFFBEB':q.r===3?'#ECFDF5':'#F3F4F6',color:q.r===1?'#EF4444':q.r===2?'#F59E0B':q.r===3?'#10B981':'#6B7280',width:'28px',height:'28px',display:'flex',alignItems:'center',justifyContent:'center',borderRadius:'8px',fontWeight:700}">{{q.r}}</span><span style="flex:1;color:#374151;font-weight:600">{{q.t}}</span><span style="color:#9CA3AF">{{q.c}}次</span><div style="width:100px;height:8px;background:#F3F4F6;border-radius:4px;overflow:hidden"><div :style="{width:q.p,background:q.r===1?'#EF4444':q.r===2?'#F59E0B':q.r===3?'#10B981':'#3B82F6',height:'100%'}"/></div></div></div></template>
              <!-- Trend expanded -->
              <template v-if="expandedCard==='trend'"><h2 style="margin:0 0 24px;color:#1F2937">用户满意度趋势 · 详细</h2><div style="flex:1;min-height:400px;width:100%"><svg viewBox="0 0 100 60" preserveAspectRatio="none" style="width:100%;height:100%"><g stroke="rgba(0,0,0,0.06)" stroke-width=".4"><line x1="10" y1="50" x2="95" y2="50"/><line x1="10" y1="38" x2="95" y2="38"/><line x1="10" y1="26" x2="95" y2="26"/><line x1="10" y1="14" x2="95" y2="14"/></g><g fill="#9CA3AF" font-size="3.5" text-anchor="end"><text x="9" y="13">100</text><text x="9" y="25">95</text><text x="9" y="37">90</text><text x="9" y="49">85</text></g><g fill="#9CA3AF" font-size="3.5" text-anchor="middle"><text x="20" y="56">05.01</text><text x="41" y="56">05.10</text><text x="62" y="56">05.20</text><text x="83" y="56">05.30</text></g><defs><linearGradient id="g3" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="rgba(59,130,246,0.3)"/><stop offset="100%" stop-color="rgba(59,130,246,0)"/></linearGradient></defs><path d="M10,48 L20,40 L30,42 L40,25 L50,30 L60,15 L70,20 L80,12 L95,10 L95,50 L10,50 Z" fill="url(#g3)"/><polyline points="10,48 20,40 30,42 40,25 50,30 60,15 70,20 80,12 95,10" fill="none" stroke="#3B82F6" stroke-width="1.2"/></svg></div></template>
              <!-- Cloud expanded -->
              <template v-if="expandedCard==='cloud'"><h2 style="margin:0 0 24px;color:#1F2937">游客关注词云 · 详细</h2><div class="cloud cloud-lg"><span class="cw c1">路线</span><span class="cw c2">表演时间</span><span class="cw c3">美食</span><span class="cw c4">门票</span><span class="cw c5">天气</span><span class="cw c6">洗手间</span><span class="cw c7">停车</span><span class="cw c4">地铁</span><span class="cw c5">优惠</span><span class="cw c6">景点</span><span class="cw c7">排队</span><span class="cw c3">导览</span><span class="cw c4">卫生间</span><span class="cw c5">纪念品</span><span class="cw c2">演出</span><span class="cw c1" style="font-size:38px;color:#EF4444">失物招领</span><span class="cw c2" style="font-size:30px;color:#10B981">行李寄存</span><span class="cw c5" style="font-size:16px;color:#3B82F6">地图</span></div></template>
              <!-- Sentiment expanded -->
              <template v-if="expandedCard==='sentiment'"><h2 style="margin:0 0 24px;color:#1F2937">情感分析 · 详细</h2><div style="display:flex;align-items:center;gap:40px;flex:1"><div style="width:180px;height:180px"><svg viewBox="0 0 36 36" width="100%"><path d="M18 2a16 16 0 110 32 16 16 0 010-32" fill="none" stroke="#E5E7EB" stroke-width="4"/><path d="M18 2a16 16 0 110 32" fill="none" stroke="#10B981" stroke-width="4" stroke-dasharray="75,100"/><path d="M18 2a16 16 0 010 32" fill="none" stroke="#F59E0B" stroke-width="4" stroke-dasharray="12,100" stroke-dashoffset="-75"/><text x="18" y="20.5" font-size="7" text-anchor="middle" fill="#1F2937" font-weight="700">75%</text></svg></div><div style="display:flex;flex-direction:column;gap:12px;font-size:14px"><div style="display:flex;align-items:center;gap:8px"><span style="width:12px;height:12px;border-radius:3px;background:#10B981"/><span style="color:#374151">正面 (75%)</span></div><div style="display:flex;align-items:center;gap:8px"><span style="width:12px;height:12px;border-radius:3px;background:#F59E0B"/><span style="color:#374151">中性 (12%)</span></div><div style="display:flex;align-items:center;gap:8px"><span style="width:12px;height:12px;border-radius:3px;background:#EF4444"/><span style="color:#374151">负面 (13%)</span></div></div></div></template>
              <!-- Feedback expanded -->
              <template v-if="expandedCard==='feedback'">
                <h2 style="margin:0 0 24px;color:#1F2937">最新服务建议 · 详细回复</h2>
                <div class="fb-expand-list">
                  <div v-for="(f,i) in [{t:'10:42',txt:'建议增加英文导览语音选项。'},{t:'09:15',txt:'路线规划很准，但希望标识更明显。'},{t:'昨天',txt:'数字人很有趣，孩子很喜欢。'},{t:'前天',txt:'门票兑换流程简化较好。'},{t:'3天前',txt:'希望能增加AR导航功能。'}]" :key="i" class="fb-expand-item">
                    <div class="fb-content-row">
                      <span class="fb-t">{{f.t}}</span>
                      <span class="fb-txt">{{f.txt}}</span>
                      <button class="fb-reply-trigger" @click="replyingTo = replyingTo === i ? null : i">回复</button>
                    </div>
                    <transition name="slide-down">
                      <div v-if="replyingTo === i" class="fb-reply-box">
                        <textarea v-model="replyText" class="fb-textarea" placeholder="输入回复内容..."></textarea>
                        <button class="fb-submit" :disabled="!replyText.trim()" @click="handleReply(i)">发送回复</button>
                      </div>
                    </transition>
                  </div>
                </div>
              </template>
            </div>
          </div>
        </transition>
      </main>

      <!-- ==================== API CONFIG VIEW ==================== -->
      <main v-else-if="currentView==='api'" class="settings-container">
        <div class="settings-glass-card">
          <div class="sc-hd"><h2>API 与引擎配置</h2><p>管理后端驱动所需的 AI 服务及接口参数</p></div>
          <div class="sc-body">
            <div class="srow"><div class="sinfo"><h3>LLM 引擎提供商</h3><p>切换数字人后端驱动的语言模型</p></div><select class="ssel"><option>DeepSeek</option><option>通义千问</option><option>OpenAI (兼容)</option></select></div>
            <div class="srow"><div class="sinfo"><h3>LLM 默认模型</h3><p>当前 provider 的默认模型变体</p></div><select class="ssel"><option>deepseek-chat</option><option>deepseek-reasoner</option></select></div>
            <div class="srow"><div class="sinfo"><h3>TTS 语音引擎</h3><p>数字人流式语音合成服务</p></div><select class="ssel"><option>阿里云 NLS</option><option>Azure TTS</option><option>讯飞流式</option></select></div>
            <div class="srow"><div class="sinfo"><h3>ASR 语音识别</h3><p>用户语音输入识别引擎</p></div><select class="ssel"><option>阿里云 ASR</option><option>讯飞流式 ASR</option><option>Whisper (本地)</option></select></div>
            <div class="srow"><div class="sinfo"><h3>Embedding 模型</h3><p>知识库向量化模型</p></div><select class="ssel"><option>text-embedding-v3</option><option>BGE-M3</option><option>OpenAI text-embedding-3</option></select></div>
            <div class="srow"><div class="sinfo"><h3>Web Search 服务</h3><p>互联网检索兜底提供商</p></div><select class="ssel"><option>Bocha (中文优化)</option><option>Tavily</option></select></div>
            <div class="srow"><div class="sinfo"><h3>每日搜索配额</h3><p>Web Search 每日调用上限</p></div><input type="number" value="200" class="sinput" /></div>
            <div class="srow"><div class="sinfo"><h3>API Key 状态</h3><p>各 Provider 密钥不显示，仅展示配置与否</p></div><div style="display:flex;flex-direction:column;gap:6px;font-size:13px"><span style="color:#10B981">✅ DeepSeek</span><span style="color:#10B981">✅ 阿里云 NLS</span><span style="color:#F59E0B">⚠️ Tavily 未配置</span></div></div>
          </div>
          <div class="sc-actions"><button class="pbtn" @click="currentView='dashboard'">返回</button></div>
        </div>
      </main>

      <!-- ==================== SYSTEM SETTINGS VIEW ==================== -->
      <main v-else-if="currentView==='settings'" class="settings-container">
        <div class="settings-glass-card">
          <div class="sc-hd"><h2>全局系统设置</h2><p>管理整个系统的通用外观与行为配置</p></div>
          <div class="sc-body">
            <div class="srow"><div class="sinfo"><h3>全局背景主题</h3><p>上传图片以更改管理端与用户端的主题背景</p></div><button class="upbtn" @click="fileInput?.click()">更换图片</button><input type="file" ref="fileInput" @change="handleBgUpload" accept="image/*" style="display:none"/></div>
            <div class="srow"><div class="sinfo"><h3>语音持久化</h3><p>是否保存用户语音录音文件</p></div><div class="tgl active"><div class="tgl-knob"/></div></div>
            <div class="srow"><div class="sinfo"><h3>用户文档配额</h3><p>每用户最多上传文档数</p></div><input type="number" value="100" class="sinput" /></div>
          </div>
          <div class="sc-actions"><button class="pbtn" @click="currentView='dashboard'">保存并返回</button></div>
        </div>
      </main>
    </div>
  </div>
</template>

<style>
/* ===== ROOT RESPONSIVE ===== */
.admin-root { width:100vw; height:100vh; background:#000; display:flex; justify-content:center; align-items:center; font-family:'Inter',system-ui,-apple-system,sans-serif; overflow:hidden }
/* Using dynamic aspect ratio scaling based on viewport width/height to avoid excessive scaling */
.layout-wrapper {
  width: 100%;
  max-width: 1920px;
  height: 100%;
  max-height: 1080px;
  position: relative;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  box-shadow: 0 0 30px rgba(0,0,0,.5);
  overflow: hidden;
}
@media (min-width: 1921px) or (min-height: 1081px) {
  .layout-wrapper {
    aspect-ratio: 16/9;
    height: auto;
    width: auto;
    min-width: 1280px;
    min-height: 720px;
  }
}
.fullscreen-bg { position:absolute; top:0; left:0; width:100%; height:100%; object-fit:cover; z-index:0; filter:brightness(.85) contrast(1.05) }

/* ===== NAVBAR ===== */
.navbar { width:100%; height:80px; display:flex; flex-direction:row; justify-content:space-between; align-items:center; padding:0 40px; background:rgba(255,255,255,.4); backdrop-filter:blur(20px); -webkit-backdrop-filter:blur(20px); border-bottom:1px solid rgba(255,255,255,.3); box-sizing:border-box; flex-shrink:0; z-index:10 }
.logo-zone { display:flex; align-items:center; gap:12px }
.logo-icon { width:32px; height:32px; color:#1E3A8A }
.logo-text { display:flex; flex-direction:column }
.logo-cn { font-size:18px; font-weight:600; color:#1F2937; line-height:1.2 }
.logo-en { font-size:11px; color:#4B5563; line-height:1 }
.nav-menu { display:flex; gap:8px; background:rgba(255,255,255,.5); border-radius:40px; padding:8px; backdrop-filter:blur(10px); border:1px solid rgba(255,255,255,.4); box-shadow:0 4px 12px rgba(0,0,0,.05) }
.nav-item { padding:10px 32px; border-radius:30px; background:transparent; color:#4B5563; font-size:15px; font-weight:600; border:none; cursor:pointer; transition:all .2s; font-family:inherit; outline:none }
.nav-item:hover { background:rgba(255,255,255,.4) }
.nav-item.active { background:#FFF; color:#1E3A8A; box-shadow:0 4px 8px rgba(0,0,0,.08) }
.user-glass { display:flex; align-items:center; gap:12px; background:rgba(255,255,255,.5); backdrop-filter:blur(20px); -webkit-backdrop-filter:blur(20px); padding:6px 16px 6px 6px; border-radius:40px; border:1px solid rgba(255,255,255,.6); box-shadow:0 4px 12px rgba(0,0,0,.05) }
.bell-btn { width:36px; height:36px; border-radius:50%; background:rgba(255,255,255,.8); display:flex; justify-content:center; align-items:center; border:none; cursor:pointer; padding:0; transition:all .2s; outline:none }
.bell-btn:hover { background:#FFF }
.text-avatar { width:36px; height:36px; border-radius:50%; background:#1E3A8A; color:#FFF; display:flex; align-items:center; justify-content:center; font-weight:700; font-size:18px; box-shadow:0 2px 8px rgba(30,58,138,.3) }
.username { font-size:14px; font-weight:600; color:#1F2937 }

/* ===== MAIN CONTAINER ===== */
.main-container { width:100%; flex:1; display:flex; flex-direction:row; padding:24px 40px; gap:24px; box-sizing:border-box; overflow:hidden; z-index:10; position:relative }

/* ===== PEEK HANDLES ===== */
.peek { position:absolute; top:50%; width:28px; height:90px; background:rgba(255,255,255,.85); backdrop-filter:blur(12px); -webkit-backdrop-filter:blur(12px); display:flex; align-items:center; justify-content:center; cursor:pointer; z-index:50; opacity:0; pointer-events:none; transition:all .3s cubic-bezier(.4,0,.2,1); color:#4B5563; box-shadow:0 8px 24px rgba(0,0,0,.12); border:1px solid rgba(255,255,255,.9) }
.peek.show { opacity:1; pointer-events:auto }
.left-peek { left:0; border-radius:0 14px 14px 0; border-left:none }
.left-peek.show { transform:translateY(-50%) }
.left-peek.show:hover { transform:translateY(-50%) translateX(4px) }
.right-peek { right:0; border-radius:14px 0 0 14px; border-right:none }
.right-peek.show { transform:translateY(-50%) }
.right-peek.show:hover { transform:translateY(-50%) translateX(-4px) }

/* ===== LEFT PANEL ===== */
.left-panel { flex:1; max-width:380px; min-width:300px; height:100%; background:rgba(255,255,255,.7); backdrop-filter:blur(30px); -webkit-backdrop-filter:blur(30px); border-radius:24px; padding:24px; display:flex; flex-direction:column; gap:20px; box-shadow:0 8px 32px rgba(0,0,0,.1); border:1px solid rgba(255,255,255,.6); box-sizing:border-box; transition:all .4s cubic-bezier(.4,0,.2,1); overflow:hidden; transform-origin:left center }
.left-panel.hidden { flex:0 0 0; min-width:0; max-width:0; padding:0; margin:0; border:none; opacity:0; overflow:hidden }
.panel-hd { display:flex; justify-content:space-between; align-items:center }
.panel-hd h3 { margin:0; font-size:18px; font-weight:700; color:#1F2937; white-space:nowrap }
.icon-btn { background:rgba(255,255,255,.5); border:1px solid rgba(255,255,255,.8); color:#4B5563; cursor:pointer; padding:8px; border-radius:50%; display:flex; align-items:center; justify-content:center; transition:all .2s }
.icon-btn:hover { background:rgba(255,255,255,.9); color:#1F2937 }

/* Persona Cards */
.persona-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px }
.persona-card { aspect-ratio:9/16; border-radius:16px; overflow:hidden; position:relative; box-shadow:0 4px 12px rgba(0,0,0,.1); cursor:pointer; border:2px solid transparent; transition:all .2s; z-index:1 }
.persona-card.active { border-color:#3B82F6; box-shadow:0 8px 24px rgba(59,130,246,.3); z-index:2 }
.persona-card img { width:100%; height:100%; object-fit:cover; transition:transform .3s }
.persona-card:hover img { transform:scale(1.05) }
.card-name { position:absolute; bottom:0; left:0; width:100%; background:rgba(255,255,255,.65); backdrop-filter:blur(14px); -webkit-backdrop-filter:blur(14px); padding:12px 8px; text-align:center; font-size:13px; font-weight:600; color:#1F2937; border-top:1px solid rgba(255,255,255,.5); box-sizing:border-box; border-radius:0 0 14px 14px }

.setting-tabs { display:flex; background:rgba(255,255,255,.6); border-radius:12px; padding:4px }
.stab { flex:1; text-align:center; padding:8px 0; font-size:14px; color:#4B5563; cursor:pointer; border-radius:8px; transition:all .2s; white-space:nowrap }
.stab.active { background:#FFF; color:#3B82F6; font-weight:600; box-shadow:0 2px 4px rgba(0,0,0,.05) }

.setting-list { display:flex; flex-direction:column; gap:10px; flex:1; overflow-y:auto; padding-right:4px }
.sitem { display:flex; justify-content:space-between; align-items:center; padding:12px 16px; background:rgba(255,255,255,.7); border-radius:12px; font-size:14px; color:#4B5563 }
.sval { font-weight:600; color:#1F2937 }
.model-link { color:#3B82F6; cursor:pointer; text-decoration:none; padding:4px 10px; border-radius:6px; background:rgba(59,130,246,.1); transition:background .2s }
.model-link:hover { background:rgba(59,130,246,.2) }

/* Model selector dropdown */
.model-drop { background:rgba(255,255,255,.95); border-radius:12px; border:1px solid rgba(0,0,0,.08); box-shadow:0 8px 20px rgba(0,0,0,.1); padding:8px; display:flex; flex-direction:column; gap:4px }
.model-opt { padding:10px 14px; border-radius:8px; cursor:pointer; font-size:14px; color:#4B5563; transition:all .15s }
.model-opt:hover { background:#F3F4F6 }
.model-opt.sel { background:#DBEAFE; color:#1E3A8A; font-weight:600 }

/* ===== CENTER PANEL (flex:1 auto-expands to fill available space) ===== */
.center-panel { flex:2; min-width:400px; height:100%; position:relative; display:flex; justify-content:center; align-items:center; border-radius:24px; transition:all .4s cubic-bezier(.4,0,.2,1) }
.preview-box { position:absolute; inset:0; border-radius:24px; background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.15); box-shadow:0 8px 32px rgba(0,0,0,.05); display:flex; align-items:center; justify-content:center; overflow:hidden }
.sdk-holder { display:flex; flex-direction:column; align-items:center; gap:20px; padding:40px 80px; background:rgba(0,0,0,.2); backdrop-filter:blur(24px); -webkit-backdrop-filter:blur(24px); border-radius:28px; border:1px dashed rgba(255,255,255,.25) }
.ph-text { color:rgba(255,255,255,.85); font-size:20px; font-weight:500; letter-spacing:1px }

.center-actions { position:absolute; bottom:24px; display:flex; flex-wrap:wrap; justify-content:center; gap:10px; background:rgba(255,255,255,.4); backdrop-filter:blur(24px); -webkit-backdrop-filter:blur(24px); padding:8px; border-radius:30px; border:1px solid rgba(255,255,255,.5); box-shadow:0 12px 32px rgba(0,0,0,.15),inset 0 1px 1px rgba(255,255,255,.6); white-space:nowrap; max-width:90% }
.act-pill { padding:12px 22px; border-radius:24px; background:transparent; border:none; font-size:14px; font-weight:600; color:#1F2937; cursor:pointer; transition:all .2s; outline:none; font-family:inherit }
.act-pill.active { background:#FFF; color:#1E3A8A; box-shadow:0 4px 12px rgba(0,0,0,.08) }
.act-pill:hover:not(.active) { background:rgba(255,255,255,.5) }
.act-pill:active { transform:scale(.96) }

/* ===== RIGHT PANEL ===== */
.right-panel { flex:2.5; max-width:620px; min-width:450px; height:100%; background:rgba(255,255,255,.7); backdrop-filter:blur(30px); -webkit-backdrop-filter:blur(30px); border-radius:24px; border:1px solid rgba(255,255,255,.6); box-shadow:0 8px 32px rgba(0,0,0,.1); display:flex; flex-direction:column; overflow:hidden; box-sizing:border-box; transition:all .4s cubic-bezier(.4,0,.2,1); transform-origin:right center }
.right-panel.hidden { flex:0 0 0; min-width:0; max-width:0; padding:0; margin:0; border:none; opacity:0; overflow:hidden }
.rp-inner { width:100%; flex:1; display:flex; flex-direction:column; gap:18px; padding:24px; overflow-y:auto; box-sizing:border-box; scrollbar-width:none; -ms-overflow-style:none }
.rp-inner::-webkit-scrollbar { display:none }
.rp-hd { display:flex; align-items:center; gap:12px }
.rp-hd h2 { margin:0; font-size:20px; font-weight:700; color:#1F2937; white-space:nowrap }

.date-row { display:flex; justify-content:space-between; align-items:center }
.db-tabs { display:flex; gap:4px; background:rgba(255,255,255,.8); padding:4px; border-radius:20px; box-shadow:0 2px 8px rgba(0,0,0,.05) }
.tbtn { background:transparent; color:#4B5563; padding:6px 18px; border-radius:16px; border:none; font-size:13px; font-weight:600; cursor:pointer; transition:all .2s; outline:none; font-family:inherit }
.tbtn:hover:not(.active) { background:rgba(255,255,255,.5) }
.tbtn.active { background:#3B82F6; color:#FFF; box-shadow:0 4px 12px rgba(59,130,246,.4) }

.date-picker-wrap { position:relative }
.dp-btn { display:flex; align-items:center; gap:8px; padding:7px 18px; background:rgba(255,255,255,.8); border:1px solid rgba(255,255,255,.9); border-radius:16px; font-size:13px; font-weight:600; color:#4B5563; cursor:pointer; box-shadow:0 2px 8px rgba(0,0,0,.05); font-family:inherit; outline:none; transition:all .2s }
.dp-btn:hover { background:#FFF }
.dp-btn.active { background:#3B82F6; color:#FFF; border-color:#3B82F6 }
.cal-drop { position:absolute; top:110%; right:0; width:280px; background:rgba(255,255,255,.97); backdrop-filter:blur(20px); border-radius:16px; padding:16px; box-shadow:0 12px 32px rgba(0,0,0,.15); border:1px solid rgba(255,255,255,.8); z-index:100 }
.cal-month { text-align:center; font-weight:700; color:#1F2937; font-size:15px; margin-bottom:12px }
.cal-grid { display:grid; grid-template-columns:repeat(7,1fr); gap:4px; text-align:center; font-size:13px }
.cal-dow { font-weight:600; color:#9CA3AF; margin-bottom:8px; font-size:12px }
.cal-empty { height:28px }
.cal-day { padding:7px 0; border-radius:8px; cursor:pointer; color:#4B5563; font-weight:500 }
.cal-day:hover { background:#F3F4F6 }
.cal-day.sel { background:#3B82F6; color:#FFF }
.cal-day.mid { background:#DBEAFE; color:#1E3A8A; border-radius:0 }
.cal-btns { display:flex; justify-content:flex-end; gap:8px; margin-top:14px }
.cal-btns button { padding:6px 16px; border-radius:8px; border:none; font-weight:600; font-size:13px; cursor:pointer }
.cal-btns button.ok { background:#3B82F6; color:#FFF }

/* Metric cards */
.metric-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:10px }
.mcard { background:rgba(255,255,255,.8); border-radius:16px; padding:14px; box-shadow:0 4px 12px rgba(0,0,0,.03); display:flex; flex-direction:column; transition:transform .2s ease,box-shadow .2s ease; border:1px solid rgba(255,255,255,.8); cursor:pointer }
.mcard:hover { transform:translateY(-2px); box-shadow:0 8px 24px rgba(59,130,246,.08); background:#FFF }
.mt { font-size:12px; font-weight:600; color:#6B7280 }
.mv { font-size:22px; font-weight:700; color:#1F2937; margin:6px 0; line-height:1.2 }
.mtr { font-size:11px; display:flex; align-items:center; font-weight:600; gap:4px }
.mtr.up { color:#10B981 }
.mtr.dn { color:#EF4444 }

/* Chart cards */
.charts2col { display:grid; grid-template-columns:1fr 1.2fr; gap:14px }
.charts3col { display:grid; grid-template-columns:1.2fr 1fr 1.3fr; gap:14px }
.cchart { background:rgba(255,255,255,.8); border-radius:20px; padding:18px; box-shadow:0 4px 12px rgba(0,0,0,.03); display:flex; flex-direction:column; border:1px solid rgba(255,255,255,.8); transition:transform .2s ease,box-shadow .2s ease; cursor:pointer }
.cchart:hover { transform:translateY(-2px); box-shadow:0 8px 24px rgba(59,130,246,.08); background:#FFF }
.cchart h3 { margin:0 0 14px; font-size:15px; font-weight:700; color:#1F2937 }

.top5-list { display:flex; flex-direction:column; gap:10px }
.t5row { display:flex; align-items:center; font-size:13px; padding:2px 0 }
.t5idx { width:22px; height:22px; display:flex; align-items:center; justify-content:center; border-radius:6px; font-size:12px; font-weight:700; margin-right:10px }
.r1 { background:#FEF2F2; color:#EF4444 }
.r2 { background:#FFFBEB; color:#F59E0B }
.r3 { background:#ECFDF5; color:#10B981 }
.r4,.r5 { background:#F3F4F6; color:#6B7280 }
.t5txt { flex:1; color:#374151; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; font-weight:600 }
.t5cnt { color:#9CA3AF; font-size:12px; font-weight:600 }

.cloud { flex:1; display:flex; flex-wrap:wrap; align-items:center; justify-content:center; align-content:center; gap:8px 14px }
.cloud-lg { gap:14px 24px; padding:20px }
.cw { font-weight:600; line-height:1.3; cursor:default; transition:transform .2s }
.cw:hover { transform:scale(1.15) }
.c1 { font-size:24px; color:#3B82F6; order:1 }
.c2 { font-size:21px; color:#F59E0B; order:2 }
.c3 { font-size:19px; color:#10B981; order:3 }
.c4 { font-size:16px; color:#8B5CF6; order:4 }
.c5 { font-size:14px; color:#6B7280; order:5 }
.c6 { font-size:12px; color:#9CA3AF; order:6 }
.c7 { font-size:11px; color:#C4C4C4; order:7 }
.cloud-lg .c1 { font-size:42px } .cloud-lg .c2 { font-size:34px } .cloud-lg .c3 { font-size:28px }
.cloud-lg .c4 { font-size:22px } .cloud-lg .c5 { font-size:18px } .cloud-lg .c6 { font-size:15px } .cloud-lg .c7 { font-size:13px }

.donut { flex:1; display:flex; align-items:center; justify-content:center; padding:8px }
.fb-list { display:flex; flex-direction:column; gap:10px }
.fbi { display:flex; flex-direction:column; gap:3px; padding-bottom:10px; border-bottom:1px solid rgba(0,0,0,.04) }
.fbi:last-child { border-bottom:none; padding-bottom:0 }
.fbt { font-size:11px; color:#9CA3AF; font-weight:600 }
.fbtxt { font-size:13px; color:#4B5563; line-height:1.5; font-weight:500 }

/* ===== EXPAND OVERLAY ===== */
.expand-overlay { position:absolute; inset:0; background:rgba(0,0,0,.35); backdrop-filter:blur(16px); -webkit-backdrop-filter:blur(16px); z-index:200; display:flex; justify-content:center; align-items:center }
.expand-card { position:relative; width:75%; max-height:75%; background:rgba(255,255,255,.95); backdrop-filter:blur(40px); -webkit-backdrop-filter:blur(40px); border-radius:28px; padding:40px; box-shadow:0 24px 64px rgba(0,0,0,.25); border:1px solid rgba(255,255,255,.9); display:flex; flex-direction:column; overflow-y:auto; scrollbar-width:none; -ms-overflow-style:none }
.expand-card::-webkit-scrollbar { display:none }
.x-btn { position:absolute; top:20px; right:20px; width:44px; height:44px; border-radius:50%; background:rgba(255,255,255,.5); backdrop-filter:blur(12px); -webkit-backdrop-filter:blur(12px); border:1px solid rgba(255,255,255,.5); color:#4B5563; cursor:pointer; display:flex; align-items:center; justify-content:center; transition:all .2s }
.x-btn:hover { background:rgba(255,255,255,.9); color:#1F2937 }

/* Expanded Feedback specific */
.fb-expand-list { display:flex; flex-direction:column }
.fb-expand-item { display:flex; flex-direction:column; padding:20px 0; border-bottom:1px solid #F3F4F6 }
.fb-content-row { display:flex; align-items:center; gap:16px; font-size:16px }
.fb-t { color:#9CA3AF; font-weight:600; min-width:60px }
.fb-txt { flex:1; color:#374151; font-weight:500; line-height:1.6 }
.fb-reply-trigger { padding:8px 16px; border-radius:16px; background:#F3F4F6; color:#4B5563; font-size:14px; font-weight:600; border:none; cursor:pointer; transition:.2s }
.fb-reply-trigger:hover { background:#E5E7EB }
.fb-reply-box { display:flex; flex-direction:column; gap:12px; margin-top:16px; margin-left:76px; padding:16px; background:rgba(0,0,0,.03); border-radius:16px }
.fb-textarea { width:100%; height:80px; background:#FFF; border:1px solid rgba(0,0,0,.1); border-radius:12px; padding:12px; font-family:inherit; font-size:14px; resize:none; outline:none; box-sizing:border-box }
.fb-submit { align-self:flex-end; padding:10px 24px; border-radius:12px; background:#3B82F6; color:#FFF; font-weight:600; border:none; cursor:pointer; transition:.2s }
.fb-submit:disabled { opacity:.5; cursor:not-allowed }
.fb-submit:not(:disabled):hover { background:#2563EB }

.slide-down-enter-active, .slide-down-leave-active { transition:all .3s ease; overflow:hidden }
.slide-down-enter-from, .slide-down-leave-to { opacity:0; max-height:0; margin-top:0; padding-top:0; padding-bottom:0 }
.slide-down-enter-to, .slide-down-leave-from { opacity:1; max-height:200px }

/* ===== SETTINGS / API CONFIG PAGES ===== */
.settings-container { width:100%; flex:1; display:flex; justify-content:center; align-items:center; padding:40px; box-sizing:border-box; z-index:10 }
.settings-glass-card { width:100%; max-width:820px; background:rgba(255,255,255,.92); backdrop-filter:blur(40px); -webkit-backdrop-filter:blur(40px); border-radius:24px; border:1px solid rgba(255,255,255,.9); box-shadow:0 16px 48px rgba(0,0,0,.1); padding:48px; display:flex; flex-direction:column; gap:32px; max-height:90%; overflow-y:auto; scrollbar-width:none; -ms-overflow-style:none }
.settings-glass-card::-webkit-scrollbar { display:none }
.sc-hd { border-bottom:1px solid rgba(0,0,0,.08); padding-bottom:20px }
.sc-hd h2 { font-size:26px; font-weight:700; color:#1F2937; margin:0 0 6px }
.sc-hd p { font-size:14px; color:#6B7280; margin:0 }
.sc-body { display:flex; flex-direction:column; gap:14px }
.srow { display:flex; justify-content:space-between; align-items:center; background:rgba(255,255,255,.5); padding:20px; border-radius:16px; border:1px solid rgba(0,0,0,.04) }
.sinfo h3 { margin:0 0 4px; font-size:15px; font-weight:600; color:#1F2937 }
.sinfo p { margin:0; font-size:12px; color:#6B7280 }
.ssel { padding:10px 14px; border-radius:12px; border:1px solid rgba(0,0,0,.1); background:#FFF; font-size:13px; color:#1F2937; font-weight:500; outline:none; cursor:pointer; min-width:150px }
.sinput { width:80px; padding:10px 12px; border-radius:12px; border:1px solid rgba(0,0,0,.1); background:#FFF; font-size:13px; color:#1F2937; outline:none; text-align:center }
.upbtn { padding:10px 24px; background:#3B82F6; color:#FFF; border:none; border-radius:12px; font-size:13px; font-weight:600; cursor:pointer; box-shadow:0 4px 12px rgba(59,130,246,.2); transition:all .2s }
.upbtn:hover { background:#2563EB; box-shadow:0 6px 16px rgba(59,130,246,.3); transform:translateY(-1px) }
.sc-actions { display:flex; justify-content:flex-end }
.pbtn { padding:14px 40px; background:#1E3A8A; color:#FFF; border:none; border-radius:16px; font-size:15px; font-weight:600; cursor:pointer; transition:all .2s }
.pbtn:hover { background:#1e40af; box-shadow:0 8px 24px rgba(30,58,138,.3) }

/* Toggle */
.tgl { width:56px; height:32px; border-radius:16px; background:rgba(0,0,0,.15); border:none; position:relative; cursor:pointer; transition:.3s; flex-shrink:0 }
.tgl.active { background:#3B82F6; box-shadow:0 0 12px rgba(59,130,246,.3) }
.tgl-knob { width:24px; height:24px; background:#FFF; border-radius:50%; position:absolute; top:4px; left:4px; transition:.3s cubic-bezier(.4,0,.2,1); box-shadow:0 2px 6px rgba(0,0,0,.2) }
.tgl.active .tgl-knob { left:28px }

/* Transitions */
.fade-enter-active,.fade-leave-active { transition:opacity .25s ease }
.fade-enter-from,.fade-leave-to { opacity:0 }

/* ===== ADMIN RESPONSIVE EXCLUDED AS REQUESTED ===== */
</style>
