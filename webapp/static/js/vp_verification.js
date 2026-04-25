/**
 * VP 验证前端 JavaScript
 */

// 全局状态
let currentVcType = 'InspectionReport';
let currentVcHash = null;
let currentUuid = null;
let vcConfig = {};

// API 基础路径
const API_BASE = '/api/vp-verification';

// DOM 元素
const elements = {};

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    cacheElements();
    bindEvents();
    checkOracleStatus();
    loadVcRecords(currentVcType);
    loadVcConfig(currentVcType);
    loadHolderCredentials(currentVcType);
});

// 缓存 DOM 元素
function cacheElements() {
    elements.vcTypeBtns = document.querySelectorAll('.vc-type-btn');
    elements.vcRecordGrid = document.getElementById('vcRecordGrid');
    elements.vcCountBadge = document.getElementById('vcCountBadge');
    elements.configCard = document.getElementById('configCard');
    elements.verifyCard = document.getElementById('verifyCard');
    elements.predicateContainer = document.getElementById('predicateContainer');
    elements.attributeFilterContainer = document.getElementById('attributeFilterContainer');
    elements.addPredicateBtn = document.getElementById('addPredicateBtn');
    elements.addAttributeFilterBtn = document.getElementById('addAttributeFilterBtn');
    elements.verifyBtn = document.getElementById('verifyBtn');
    elements.progressSection = document.getElementById('progressSection');
    elements.resultSection = document.getElementById('resultSection');
    elements.step2Progress = document.getElementById('step2Progress');
    elements.step3Progress = document.getElementById('step3Progress');
    elements.resultStatus = document.getElementById('resultStatus');
    elements.step2Result = document.getElementById('step2Result');
    elements.step3Result = document.getElementById('step3Result');
    elements.revealedAttrsList = document.getElementById('revealedAttrsList');
    elements.predicateResultsList = document.getElementById('predicateResultsList');
    elements.restrictionResultsList = document.getElementById('restrictionResultsList');
    elements.errorDetail = document.getElementById('errorDetail');
    elements.errorText = document.getElementById('errorText');
    elements.holderInfo = document.getElementById('holderInfo');
    elements.oracleStatus = document.getElementById('oracleStatus');
}

// 绑定事件
function bindEvents() {
    // VC 类型切换
    elements.vcTypeBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            switchVcType(btn.dataset.vcType);
        });
    });

    // 添加谓词
    elements.addPredicateBtn.addEventListener('click', addPredicateField);

    // 添加属性过滤器
    elements.addAttributeFilterBtn.addEventListener('click', addAttributeFilterField);

    // 执行验证
    elements.verifyBtn.addEventListener('click', executeVerification);
}

// 检查 Oracle 服务状态
async function checkOracleStatus() {
    try {
        const response = await fetch('http://localhost:7003/api/health');
        const data = await response.json();
        if (data.status === 'healthy') {
            elements.oracleStatus.classList.add('online');
        } else {
            elements.oracleStatus.classList.add('offline');
        }
    } catch (e) {
        elements.oracleStatus.classList.add('offline');
    }
}

// 切换 VC 类型
function switchVcType(vcType) {
    currentVcType = vcType;
    currentVcHash = null;
    currentUuid = null;

    // 更新按钮状态
    elements.vcTypeBtns.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.vcType === vcType);
    });

    // 隐藏配置和验证卡片
    elements.configCard.style.display = 'none';
    elements.verifyCard.style.display = 'none';

    // 加载数据
    loadVcRecords(vcType);
    loadVcConfig(vcType);
    loadHolderCredentials(vcType);
}

// 加载 VC 记录
async function loadVcRecords(vcType) {
    elements.vcRecordGrid.innerHTML = '<div class="empty-state">加载中...</div>';

    try {
        const response = await fetch(`${API_BASE}/latest-uuids?vc_type=${vcType}`);
        const data = await response.json();

        if (data.success && data.data[vcType]) {
            const records = data.data[vcType];
            elements.vcCountBadge.textContent = `${records.length} 个记录`;
            elements.vcCountBadge.style.display = 'inline-block';

            if (records.length === 0) {
                elements.vcRecordGrid.innerHTML = '<div class="empty-state">暂无记录</div>';
                return;
            }

            elements.vcRecordGrid.innerHTML = records.map((record, index) => `
                <div class="vc-record-card ${index === 0 ? 'selected' : ''}"
                     data-vc-hash="${record.vc_hash}"
                     data-uuid="${record.uuid}">
                    <div class="record-uuid">UUID: ${record.uuid}</div>
                    <div class="record-hash">${record.vc_hash}</div>
                    <div class="record-meta">
                        <span>${record.original_contract_name || 'N/A'}</span>
                        <span>${formatTimestamp(record.timestamp)}</span>
                    </div>
                </div>
            `).join('');

            // 绑定选择事件
            document.querySelectorAll('.vc-record-card').forEach(card => {
                card.addEventListener('click', () => selectVcRecord(card));
            });

            // 自动选择第一个
            if (records.length > 0) {
                selectVcRecord(document.querySelector('.vc-record-card'));
            }
        } else {
            elements.vcRecordGrid.innerHTML = '<div class="empty-state">加载失败</div>';
        }
    } catch (e) {
        console.error('加载 VC 记录失败:', e);
        elements.vcRecordGrid.innerHTML = '<div class="empty-state">加载失败</div>';
    }
}

// 选择 VC 记录
function selectVcRecord(card) {
    document.querySelectorAll('.vc-record-card').forEach(c => c.classList.remove('selected'));
    card.classList.add('selected');

    currentVcHash = card.dataset.vcHash;
    currentUuid = card.dataset.uuid;

    // 显示配置卡片
    elements.configCard.style.display = 'block';
    elements.verifyCard.style.display = 'block';

    // 滚动到配置区域
    elements.configCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// 加载 VC 配置
async function loadVcConfig(vcType) {
    try {
        const response = await fetch(`${API_BASE}/config/${vcType}`);
        const data = await response.json();

        if (data.success) {
            vcConfig = data;
            renderPredicateFields(data.predicates);
            renderAttributeFilterFields(data.attribute_filters);
        }
    } catch (e) {
        console.error('加载配置失败:', e);
    }
}

// 渲染谓词字段
function renderPredicateFields(predicates) {
    if (!predicates || Object.keys(predicates).length === 0) {
        elements.predicateContainer.innerHTML = '<div class="empty-state">当前 VC 类型无默认谓词</div>';
        return;
    }

    elements.predicateContainer.innerHTML = '';
    Object.entries(predicates).forEach(([key, pred]) => {
        const item = document.createElement('div');
        item.className = 'predicate-item';
        item.innerHTML = `
            <input type="text" value="${key}" class="pred-key" placeholder="谓词名称" readonly>
            <select class="pred-attr">
                ${getAllAttributes().map(attr => `<option value="${attr}" ${attr === pred.attribute ? 'selected' : ''}>${attr}</option>`).join('')}
            </select>
            <select class="pred-op">
                ${['>', '>=', '<', '<=', '==', '!='].map(op => `<option value="${op}" ${op === pred.operator ? 'selected' : ''}>${op}</option>`).join('')}
            </select>
            <input type="number" value="${pred.value}" class="pred-value" placeholder="值">
            <button class="remove-btn" onclick="removePredicateField(this)">&times;</button>
        `;
        elements.predicateContainer.appendChild(item);
    });
}

// 渲染属性过滤器字段
function renderAttributeFilterFields(filters) {
    if (!filters || Object.keys(filters).length === 0) {
        elements.attributeFilterContainer.innerHTML = '<div class="empty-state">当前 VC 类型无默认属性过滤器</div>';
        return;
    }

    elements.attributeFilterContainer.innerHTML = '';
    Object.entries(filters).forEach(([attr, value]) => {
        const item = document.createElement('div');
        item.className = 'attribute-filter-item';
        item.innerHTML = `
            <input type="text" value="${attr}" class="filter-attr" placeholder="属性名" readonly>
            <input type="text" value="${value}" class="filter-value" placeholder="属性值">
            <button class="remove-btn" onclick="removeAttributeFilterField(this)">&times;</button>
        `;
        elements.attributeFilterContainer.appendChild(item);
    });
}

// 获取所有属性
function getAllAttributes() {
    return vcConfig.all_attributes || [];
}

// 添加谓词字段
function addPredicateField() {
    if (elements.predicateContainer.querySelector('.empty-state')) {
        elements.predicateContainer.innerHTML = '';
    }

    const item = document.createElement('div');
    item.className = 'predicate-item';
    item.innerHTML = `
        <input type="text" class="pred-key" placeholder="谓词名称">
        <select class="pred-attr">
            ${getAllAttributes().map(attr => `<option value="${attr}">${attr}</option>`).join('')}
        </select>
        <select class="pred-op">
            <option value=">">&gt;</option>
            <option value=">=">&ge;</option>
            <option value="<">&lt;</option>
            <option value="<=">&le;</option>
            <option value="==">=</option>
            <option value="!=">&ne;</option>
        </select>
        <input type="text" class="pred-value" placeholder="值">
        <button class="remove-btn" onclick="removePredicateField(this)">&times;</button>
    `;
    elements.predicateContainer.appendChild(item);
}

// 移除谓词字段
function removePredicateField(btn) {
    btn.parentElement.remove();
    if (elements.predicateContainer.children.length === 0) {
        elements.predicateContainer.innerHTML = '<div class="empty-state">当前 VC 类型无默认谓词</div>';
    }
}

// 添加属性过滤器字段
function addAttributeFilterField() {
    if (elements.attributeFilterContainer.querySelector('.empty-state')) {
        elements.attributeFilterContainer.innerHTML = '';
    }

    const item = document.createElement('div');
    item.className = 'attribute-filter-item';
    item.innerHTML = `
        <select class="filter-attr">
            ${getAllAttributes().map(attr => `<option value="${attr}">${attr}</option>`).join('')}
        </select>
        <input type="text" class="filter-value" placeholder="属性值">
        <button class="remove-btn" onclick="removeAttributeFilterField(this)">&times;</button>
    `;
    elements.attributeFilterContainer.appendChild(item);
}

// 移除属性过滤器字段
function removeAttributeFilterField(btn) {
    btn.parentElement.remove();
    if (elements.attributeFilterContainer.children.length === 0) {
        elements.attributeFilterContainer.innerHTML = '<div class="empty-state">当前 VC 类型无默认属性过滤器</div>';
    }
}

// 加载 Holder 凭证
async function loadHolderCredentials(vcType) {
    elements.holderInfo.innerHTML = '<div class="empty-state">加载中...</div>';

    try {
        const response = await fetch(`${API_BASE}/holder-credentials/${vcType}`);
        const data = await response.json();

        if (data.success) {
            if (data.count === 0) {
                elements.holderInfo.innerHTML = '<div class="empty-state">Holder 暂无此类型凭证</div>';
            } else {
                elements.holderInfo.innerHTML = `
                    <div style="font-size: 0.85rem; color: var(--text-muted);">
                        Holder 拥有 <strong style="color: var(--primary-color);">${data.count}</strong> 个 ${vcType} 类型凭证
                    </div>
                `;
            }
        } else {
            elements.holderInfo.innerHTML = '<div class="empty-state">加载失败</div>';
        }
    } catch (e) {
        console.error('加载 Holder 凭证失败:', e);
        elements.holderInfo.innerHTML = '<div class="empty-state">加载失败</div>';
    }
}

// 执行验证
async function executeVerification() {
    if (!currentVcHash || !currentUuid) {
        alert('请先选择 VC 记录');
        return;
    }

    // 收集谓词条件
    const predicates = {};
    document.querySelectorAll('.predicate-item').forEach(item => {
        const key = item.querySelector('.pred-key').value.trim();
        const attr = item.querySelector('.pred-attr').value;
        const op = item.querySelector('.pred-op').value;
        const value = item.querySelector('.pred-value').value;

        if (key && attr && op && value) {
            predicates[key] = {
                attribute: attr,
                operator: op,
                value: isNaN(value) ? value : parseInt(value)
            };
        }
    });

    // 收集属性过滤器
    const attributeFilters = {};
    document.querySelectorAll('.attribute-filter-item').forEach(item => {
        const attr = item.querySelector('.filter-attr').value;
        const value = item.querySelector('.filter-value').value;

        if (attr && value) {
            attributeFilters[attr] = value;
        }
    });

    // 显示进度
    elements.progressSection.style.display = 'block';
    elements.resultSection.style.display = 'none';
    resetProgressIndicators();

    // 设置步骤 2 为运行中
    setStepStatus(elements.step2Progress, 'running');

    try {
        const response = await fetch(`${API_BASE}/validate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                vc_type: currentVcType,
                vc_hash: currentVcHash,
                uuid: currentUuid,
                predicates: Object.keys(predicates).length > 0 ? predicates : undefined,
                attribute_filters: Object.keys(attributeFilters).length > 0 ? attributeFilters : undefined
            })
        });

        const result = await response.json();

        // 更新进度
        setStepStatus(elements.step2Progress, result.step2_result?.verified ? 'completed' : 'failed');
        setStepStatus(elements.step3Progress, result.step3_result?.verified ? 'completed' : 'failed');

        // 显示结果
        displayResult(result);

    } catch (e) {
        console.error('验证失败:', e);
        setStepStatus(elements.step2Progress, 'failed');
        setStepStatus(elements.step3Progress, 'failed');
        displayResult({
            success: false,
            error: e.message
        });
    }
}

// 重置进度指示器
function resetProgressIndicators() {
    [elements.step2Progress, elements.step3Progress].forEach(step => {
        step.querySelector('.step-indicator').className = 'step-indicator pending';
    });
}

// 设置步骤状态
function setStepStatus(stepElement, status) {
    const indicator = stepElement.querySelector('.step-indicator');
    indicator.className = `step-indicator ${status}`;
}

// 显示验证结果
function displayResult(result) {
    elements.resultSection.style.display = 'block';
    elements.resultSection.scrollIntoView({ behavior: 'smooth', block: 'start' });

    // 总体状态
    elements.resultStatus.className = `result-status ${result.success ? 'success' : 'failed'}`;
    elements.resultStatus.querySelector('.status-text').textContent = result.success ? '验证成功' : '验证失败';

    // 步骤 2 结果
    if (result.step2_result) {
        elements.step2Result.style.display = 'block';
        const content = elements.step2Result.querySelector('.result-content');
        content.innerHTML = result.step2_result.verified
            ? '<div style="color: var(--success-color);">✓ UUID 匹配验证通过</div>'
            : `<div style="color: var(--danger-color);">✗ ${result.step2_result.error || '验证失败'}</div>`;
    }

    // 步骤 3 结果
    if (result.step3_result) {
        elements.step3Result.style.display = 'block';

        // 披露的属性
        const revealed = result.step3_result.revealed_attributes || {};
        if (Object.keys(revealed).length > 0) {
            elements.revealedAttrsList.innerHTML = Object.entries(revealed).map(([name, value]) => `
                <li>
                    <span class="attr-name">${name}</span>
                    <span class="attr-value">${value}</span>
                </li>
            `).join('');
        } else {
            elements.revealedAttrsList.innerHTML = '<li><span class="attr-name">无披露属性</span></li>';
        }

        // 谓词验证结果
        const predicates = result.step3_result.predicate_results || {};
        if (Object.keys(predicates).length > 0) {
            elements.predicateResultsList.innerHTML = Object.entries(predicates).map(([key, pred]) => `
                <li>
                    <span class="attr-name">${key}: ${pred.attribute} ${pred.operator} ${pred.value}</span>
                    <span class="${pred.satisfied ? 'satisfied-true' : 'satisfied-false'}">
                        ${pred.satisfied ? '✓ 满足' : '✗ 不满足'}
                    </span>
                </li>
            `).join('');
        } else {
            elements.predicateResultsList.innerHTML = '<li><span class="attr-name">无谓词验证</span></li>';
        }

        // 限制条件验证结果
        const restrictions = result.step3_result.restriction_results || {};
        if (Object.keys(restrictions).length > 0) {
            elements.restrictionResultsList.innerHTML = Object.entries(restrictions).map(([key, restr]) => `
                <li>
                    <span class="attr-name">${key}: ${restr.attribute}=${restr.expected_value}</span>
                    <span class="${restr.satisfied ? 'satisfied-true' : 'satisfied-false'}">
                        ${restr.satisfied ? '✓ 满足' : '✗ 不满足'}
                    </span>
                </li>
            `).join('');
        } else {
            elements.restrictionResultsList.innerHTML = '<li><span class="attr-name">无限制条件</span></li>';
        }
    }

    // 错误信息
    if (result.error) {
        elements.errorDetail.style.display = 'block';
        elements.errorText.textContent = result.error;
    } else {
        elements.errorDetail.style.display = 'none';
    }
}

// 格式化时间戳
function formatTimestamp(timestamp) {
    if (!timestamp) return 'N/A';
    const date = new Date(timestamp);
    return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}
