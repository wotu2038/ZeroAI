<template>
  <a-card>
    <template #title>
        <span>文档管理</span>
    </template>

    <!-- 五个Tab页 -->
    <a-tabs v-model:activeKey="activeTab">
      <!-- Tab 1: 文档上传与验证 -->
      <a-tab-pane key="upload" tab="步骤1: 文档上传与验证">
        <div class="step-content">
          <!-- 搜索和筛选栏 -->
          <div style="margin-bottom: 16px; display: flex; gap: 16px; align-items: center; flex-wrap: wrap">
            <a-input-search
              v-model:value="searchKeyword"
              placeholder="搜索文件名或路径"
              style="width: 300px"
              @search="handleSearch"
              allow-clear
            />
            <a-select
              v-model:value="filterStatus"
              placeholder="筛选状态"
              style="width: 150px"
              allow-clear
              @change="handleFilter"
            >
              <a-select-option value="validated">已验证</a-select-option>
              <a-select-option value="parsing">解析中</a-select-option>
              <a-select-option value="parsed">已解析</a-select-option>
              <a-select-option value="chunking">分块中</a-select-option>
              <a-select-option value="chunked">已分块</a-select-option>
              <a-select-option value="completed">已完成</a-select-option>
              <a-select-option value="error">错误</a-select-option>
            </a-select>
          <a-upload
            :before-upload="handleUpload"
            :file-list="uploadFileList"
            accept=".docx"
            :max-count="1"
            :disabled="uploadProcessing"
            :show-upload-list="false"
          >
              <a-button type="primary" :loading="uploadProcessing">
                <template #icon><UploadOutlined /></template>
                上传 Word 文档
              </a-button>
            </a-upload>
            <a-button @click="loadDocumentList" :loading="loading">
              <template #icon><ReloadOutlined /></template>
              刷新
            </a-button>
          </div>

          <!-- 文档列表 -->
    <a-table
      :columns="columns"
            :data-source="documents"
      :loading="loading"
      :pagination="pagination"
      row-key="id"
      @change="handleTableChange"
    >
      <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'file_name'">
                <span>{{ record.file_name }}</span>
              </template>
              <template v-if="column.key === 'file_size'">
                {{ formatFileSize(record.file_size) }}
              </template>
              <template v-if="column.key === 'status'">
                <a-tag :color="getStatusColor(record.status)">
                  {{ getStatusText(record.status) }}
                </a-tag>
              </template>
              <template v-if="column.key === 'upload_time'">
                {{ formatDateTime(record.upload_time) }}
              </template>
        <template v-if="column.key === 'action'">
          <a-space>
                  <a-button 
                    v-if="['parsed', 'chunked', 'completed'].includes(record.status)"
                    type="link" 
                    size="small" 
                    @click="handleViewParsedContent(record)"
                  >
                    查看解析结果
                  </a-button>
                  <a-button type="link" size="small" @click="handleReupload(record)">
                    重新上传
                  </a-button>
                  <a-button type="link" size="small" danger @click="handleDelete(record)">
                    删除
                  </a-button>
          </a-space>
        </template>
      </template>
    </a-table>
        </div>
      </a-tab-pane>

      <!-- Tab 2: 文档解析 -->
      <a-tab-pane key="parse" tab="步骤2: 文档解析">
        <div class="step-content">
          <a-alert
            message="文档解析"
            description="提取文字、图片、链接、表格、OLE对象、元数据"
            type="info"
            show-icon
            style="margin-bottom: 24px"
          />
          
          <!-- 文件选择和解析操作 -->
          <div style="margin-bottom: 24px; display: flex; gap: 16px; align-items: center; flex-wrap: wrap">
            <a-select
              v-model:value="selectedUploadId"
              placeholder="选择已上传的文件"
              style="width: 400px"
              :loading="loadingUploadList"
              :disabled="parsing"
              @change="handleFileSelect"
            >
              <a-select-option
                v-for="doc in uploadedDocuments"
                :key="doc.id"
                :value="doc.id"
              >
                {{ doc.file_name }} ({{ formatFileSize(doc.file_size) }}) - {{ getStatusText(doc.status) }}
              </a-select-option>
            </a-select>
            <a-button
              type="primary"
              :loading="parsing"
              :disabled="!selectedUploadId"
              @click="handleParse"
            >
              实时解析
            </a-button>
            <a-button
              @click="loadUploadedDocuments"
              :loading="loadingUploadList"
    >
              <template #icon><ReloadOutlined /></template>
              刷新列表
            </a-button>
          </div>

          <!-- 解析结果 -->
          <div v-if="parseResult" style="margin-top: 16px">
            <div style="margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
              <div style="color: #666; font-size: 12px;">
                <span v-if="parseResult.parsed_content">字符数: {{ parseResult.parsed_content?.length || 0 }}</span>
                <span v-if="parseResult?.statistics" style="margin-left: 16px;">
                  章节数: {{ parseResult.statistics.total_sections }}
                </span>
                <span style="margin-left: 16px; color: #1890ff;">（从原始Word文档实时解析）</span>
              </div>
              <a-button 
                type="primary" 
                size="small" 
                @click="handleParse"
                :loading="parsing"
                :disabled="!selectedUploadId"
              >
                <template #icon><ReloadOutlined /></template>
                重新解析
              </a-button>
            </div>
            <a-spin :spinning="parsing">
              <a-card v-if="parseResult && parseResult.parsed_content">
                <a-tabs v-model:activeKey="contentViewTab">
                  <!-- Tab 1: 原始文档 -->
                  <a-tab-pane key="original" tab="原始文档">
                    <div style="margin-top: 16px">
                      <div style="margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
                        <div style="color: #666; font-size: 12px;">
                          <span v-if="parseResult?.file_name">文件名: {{ parseResult.file_name }}</span>
                        </div>
                        <a-button 
                          type="primary" 
                          size="small" 
                          @click="loadWordDocument"
                          :loading="loadingWordDocument"
                        >
                          <template #icon><FileTextOutlined /></template>
                          加载Word文档
                        </a-button>
                      </div>
                      <a-spin :spinning="loadingWordDocument">
                        <div 
                          v-if="wordDocumentHtml" 
                          style="background: white; padding: 24px; border: 1px solid #d9d9d9; border-radius: 4px; max-height: calc(100vh - 300px); overflow-y: auto;"
                          class="word-document-viewer"
                          v-html="wordDocumentHtml"
                        ></div>
                        <a-empty v-else description="点击上方按钮加载Word文档" />
                      </a-spin>
                    </div>
                  </a-tab-pane>
                  
                  <!-- Tab 2: 完整对应文档 -->
                  <a-tab-pane key="parsed" tab="完整对应文档">
                    <div 
                      style="background: #f5f5f5; padding: 16px; border-radius: 4px; max-height: calc(100vh - 300px); overflow-y: auto; font-family: 'Microsoft YaHei', sans-serif; font-size: 14px; line-height: 1.8;"
                      v-html="formatMarkdown(parseResult.parsed_content, parseResult.document_id, parseResult.upload_id)"
                    ></div>
                  </a-tab-pane>
                  
                  <!-- Tab 3: 总结文档 -->
                  <a-tab-pane key="summary" tab="总结文档" :disabled="!parseResult.summary_content">
                    <div v-if="parseResult.summary_content"
                      style="background: #f5f5f5; padding: 16px; border-radius: 4px; max-height: calc(100vh - 300px); overflow-y: auto; font-family: 'Microsoft YaHei', sans-serif; font-size: 14px; line-height: 1.8;"
                      v-html="formatMarkdown(parseResult.summary_content, parseResult.document_id, parseResult.upload_id)"
                    ></div>
                    <a-empty v-else description="总结文档暂不可用" />
                  </a-tab-pane>
                  
                  <!-- Tab 4: 结构化数据 -->
                  <a-tab-pane key="structured" tab="结构化数据" :disabled="!parseResult.structured_content || parseResult.structured_content.length === 0">
                    <div v-if="parseResult.structured_content && parseResult.structured_content.length > 0">
                      <div style="display: flex; justify-content: flex-end; margin-bottom: 8px;">
                        <a-button size="small" type="primary" ghost @click="downloadParseStructured">
                          <template #icon><DownloadOutlined /></template>
                          下载
                        </a-button>
                      </div>
                      <pre 
                        style="background: #1e1e1e; color: #d4d4d4; padding: 16px; border-radius: 4px; max-height: calc(100vh - 340px); overflow: auto; font-family: 'Consolas', 'Monaco', monospace; font-size: 12px; line-height: 1.5; white-space: pre-wrap; word-wrap: break-word;"
                      >{{ JSON.stringify(parseResult.structured_content, null, 2) }}</pre>
                    </div>
                    <a-empty v-else description="结构化数据暂不可用" />
                  </a-tab-pane>
                </a-tabs>
              </a-card>
              <a-empty v-else description="实时解析内容不可用" />
            </a-spin>
          </div>

          <!-- 空状态 -->
          <a-empty
            v-else-if="!parsing && !loadingUploadList"
            description="请选择文件并点击'实时解析'按钮"
          />
        </div>
      </a-tab-pane>

      <!-- Tab 3: 版本管理 -->
      <a-tab-pane key="version" tab="步骤3: 版本管理">
        <div class="step-content">
          <a-alert
            message="版本管理"
            description="提取版本号、生成 group_id"
            type="info"
            show-icon
            style="margin-bottom: 24px"
          />
          
          <!-- 文档选择和操作 -->
          <div style="margin-bottom: 24px">
            <div style="display: flex; gap: 12px; align-items: center; margin-bottom: 12px">
              <a-select
                v-model:value="selectedVersionUploadId"
                placeholder="选择已解析的文档"
                style="width: 400px"
                :loading="loadingVersionList"
                show-search
                :filter-option="filterOption"
                @change="handleVersionDocumentChange"
              >
                <a-select-option
                  v-for="doc in versionDocuments"
                  :key="doc.id"
                  :value="doc.id"
                  :disabled="doc.status !== 'parsed'"
                >
                  {{ doc.file_name }} ({{ formatFileSize(doc.file_size) }}) - {{ formatDateTime(doc.upload_time) }} - {{ getStatusText(doc.status) }}
                </a-select-option>
              </a-select>
              
              <a-button
                type="primary"
                @click="handleGenerateVersion"
                :loading="generatingVersion"
                :disabled="!selectedVersionUploadId"
              >
                <template #icon><FileTextOutlined /></template>
                生成版本
              </a-button>
              
              <a-button @click="loadVersionDocuments" :loading="loadingVersionList">
                <template #icon><ReloadOutlined /></template>
                刷新列表
              </a-button>
          </div>
            
            <!-- Group ID 下拉选择框（可选） -->
            <div style="display: flex; gap: 12px; align-items: center">
              <div style="position: relative; width: 400px">
                <span style="position: absolute; left: 12px; top: 50%; transform: translateY(-50%); color: #999; font-size: 12px; z-index: 1; pointer-events: none;">Group ID:</span>
                <a-auto-complete
                  v-model:value="customGroupId"
                  placeholder="可选：选择或输入自定义 Group ID（留空则自动生成）"
                  style="width: 100%; padding-left: 80px"
                  :options="groupIdOptions"
                  :loading="loadingGroupIds"
                  :filter-option="false"
                  allow-clear
                  @search="handleGroupIdSearch"
                  @focus="loadGroupIds"
                />
              </div>
              <a-tooltip title="Group ID 只能包含字母、数字、破折号(-)和下划线(_)，例如：doc_project_20240104。可以从列表中选择已有的，也可以输入新的。">
                <QuestionCircleOutlined style="color: #999; cursor: help" />
              </a-tooltip>
            </div>
          </div>

          <!-- 版本信息显示 -->
          <a-card
            v-if="versionResult"
            title="版本信息"
            style="margin-top: 16px"
          >
            <template #extra>
              <a-button v-if="!editingVersion" type="link" @click="startEditVersion">
                <template #icon><EditOutlined /></template>
                编辑
              </a-button>
              <div v-else style="display: flex; gap: 8px">
                <a-button type="primary" size="small" @click="saveVersion" :loading="savingVersion">保存</a-button>
                <a-button size="small" @click="cancelEditVersion">取消</a-button>
              </div>
            </template>
            <a-descriptions :column="1" bordered>
              <a-descriptions-item label="文档名称">
                {{ versionResult.document_name }}
          </a-descriptions-item>
              <a-descriptions-item label="基础名称">
                <code>{{ versionResult.base_name }}</code>
          </a-descriptions-item>
              <a-descriptions-item label="版本">
                <template v-if="!editingVersion">
                  <a-tag color="blue">{{ versionResult.version }}</a-tag>
                  <span style="margin-left: 8px">(版本号: {{ versionResult.version_number }})</span>
                </template>
                <template v-else>
                  <a-input-group compact style="width: 200px">
                    <a-input
                      v-model:value="editingVersionData.version"
                      placeholder="版本"
                      style="width: 80px"
                      :maxlength="10"
                    />
                    <a-input-number
                      v-model:value="editingVersionData.version_number"
                      placeholder="版本号"
                      :min="1"
                      :max="999"
                      style="width: 120px"
                    />
                  </a-input-group>
                </template>
          </a-descriptions-item>
              <a-descriptions-item label="Group ID">
                <template v-if="!editingVersion">
                  <code style="background: #f5f5f5; padding: 4px 8px; border-radius: 4px">{{ versionResult.group_id }}</code>
                </template>
                <template v-else>
                  <a-input
                    v-model:value="editingVersionData.group_id"
                    placeholder="Group ID"
                    style="width: 100%"
                    :maxlength="100"
                    :status="groupIdValidationStatus"
                    @blur="validateGroupId(editingVersionData.group_id)"
                  />
                  <div v-if="groupIdValidationError" style="color: #ff4d4f; font-size: 12px; margin-top: 4px">
                    {{ groupIdValidationError }}
                  </div>
                </template>
          </a-descriptions-item>
              <a-descriptions-item label="日期">
                {{ versionResult.date_str }}
          </a-descriptions-item>
        </a-descriptions>
          </a-card>
          
          <a-empty
            v-else
            description="请选择已解析的文档并点击'生成版本'按钮"
          />
            </div>
      </a-tab-pane>

      <!-- Tab 4: 章节分块 -->
      <a-tab-pane key="split" tab="步骤4: 章节分块">
        <div class="step-content">
        <a-alert
            message="章节分块"
            description="按标题分块、处理超大章节"
          type="info"
            show-icon
            style="margin-bottom: 24px"
          />
          
          <!-- 文档选择和参数配置 -->
          <div style="margin-bottom: 24px">
            <div style="display: flex; gap: 12px; align-items: center; margin-bottom: 12px; flex-wrap: wrap">
              <a-select
                v-model:value="selectedSplitUploadId"
                placeholder="选择已解析的文档"
                style="width: 350px"
                :loading="loadingSplitList"
                show-search
                :filter-option="filterOption"
                @change="handleSplitDocumentChange"
              >
                <a-select-option
                  v-for="doc in splitDocuments"
                  :key="doc.id"
                  :value="doc.id"
                  :disabled="doc.status !== 'parsed'"
                >
                  {{ doc.file_name }} ({{ formatFileSize(doc.file_size) }}) - {{ formatDateTime(doc.upload_time) }} - {{ getStatusText(doc.status) }}
                </a-select-option>
              </a-select>
              
              <a-select
                v-model:value="splitStrategy"
                placeholder="选择分块策略"
                style="width: 180px"
              >
                <a-select-option value="level_1">按一级标题（推荐）</a-select-option>
                <a-select-option value="level_2">按二级标题</a-select-option>
                <a-select-option value="level_3">按三级标题</a-select-option>
                <a-select-option value="level_4">按四级标题</a-select-option>
                <a-select-option value="level_5">按五级标题</a-select-option>
                <a-select-option value="fixed_token">按固定Token</a-select-option>
                <a-select-option value="no_split">不分块</a-select-option>
              </a-select>
              
              <a-input-number
                v-model:value="maxTokensPerSection"
                placeholder="每个章节的最大token数"
                :min="1000"
                :max="20000"
                :step="1000"
                style="width: 180px"
              >
                <template #addonBefore>Max:</template>
              </a-input-number>
              
              <a-button
                type="primary"
                @click="handleSplitDocument"
                :loading="splitting"
                :disabled="!selectedSplitUploadId"
              >
                <template #icon><FileTextOutlined /></template>
                执行分块
              </a-button>
              
              <a-button @click="loadSplitDocuments" :loading="loadingSplitList">
                <template #icon><ReloadOutlined /></template>
                刷新列表
              </a-button>
            </div>
      </div>

          <!-- 分块结果 -->
          <a-card
            v-if="splitResult"
            title="分块结果"
            style="margin-top: 16px"
          >
            <!-- 统计信息 -->
            <a-descriptions title="统计信息" :column="3" bordered style="margin-bottom: 16px">
              <a-descriptions-item label="总章节数">
                <a-tag color="blue">{{ splitResult.statistics.total_sections }}</a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="总Token数">
                {{ splitResult.statistics.total_tokens.toLocaleString() }}
              </a-descriptions-item>
              <a-descriptions-item label="平均Token数">
                {{ splitResult.statistics.avg_tokens }}
              </a-descriptions-item>
              <a-descriptions-item label="最大Token数">
                <a-tag color="red">{{ splitResult.statistics.max_tokens }}</a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="最小Token数">
                <a-tag color="green">{{ splitResult.statistics.min_tokens }}</a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="超大章节数">
                <a-tag v-if="splitResult.statistics.oversized_sections_count > 0" color="orange">
                  {{ splitResult.statistics.oversized_sections_count }}
                </a-tag>
                <span v-else>0</span>
          </a-descriptions-item>
        </a-descriptions>

            <!-- 超大章节警告 -->
            <a-alert
              v-if="splitResult.statistics.oversized_sections_count > 0"
              type="warning"
              style="margin-bottom: 16px"
            >
              <template #message>
                <div>
                  <strong>超大章节警告：</strong>
                  以下 {{ splitResult.statistics.oversized_sections_count }} 个章节因超过最大token数而被分割：
                  <ul style="margin: 8px 0 0 0; padding-left: 20px">
                    <li v-for="(section, index) in splitResult.statistics.oversized_sections" :key="index">
                      {{ section }}
                    </li>
                  </ul>
            </div>
                  </template>
            </a-alert>
            
            <!-- 章节列表 -->
            <a-table
              :columns="splitColumns"
              :data-source="splitResult.sections"
              :pagination="{ pageSize: 10, showSizeChanger: true }"
              row-key="section_id"
              size="small"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'title'">
                  <span :style="{ fontWeight: record.level === 1 ? 'bold' : 'normal' }">
                    {{ record.title }}
                        </span>
                </template>
                <template v-else-if="column.key === 'token_count'">
                  <a-tag :color="getTokenCountColor(record.token_count, splitResult.max_tokens_per_section)">
                    {{ record.token_count.toLocaleString() }}
                        </a-tag>
                  </template>
                <template v-else-if="column.key === 'is_split'">
                  <a-tag v-if="record.is_split" color="orange">已分割</a-tag>
                  <span v-else>-</span>
                </template>
            </template>
            </a-table>
          </a-card>

          <a-empty
            v-else
            description="请选择已解析的文档，配置参数并点击'执行分块'按钮"
          />
        </div>
      </a-tab-pane>

      <!-- Tab 5: 创建Episode并保存到Neo4j -->
      <a-tab-pane key="process" tab="步骤5: 创建Episode并保存到Neo4j">
        <div class="step-content">
          <a-alert
            message="创建Episode并保存到Neo4j"
            description="使用Graphiti处理文档，创建Episode并提取实体和关系（方案B：文档级使用summary_content，章节级使用parsed_content）"
            type="info"
            show-icon
            style="margin-bottom: 24px"
          />
          
          <!-- 文件选择和处理操作 -->
          <div style="margin-bottom: 24px">
            <div style="display: flex; gap: 16px; align-items: center; flex-wrap: wrap; margin-bottom: 16px">
              <a-select
                v-model:value="selectedProcessUploadId"
                placeholder="选择已解析、已分块或错误的文档"
                style="width: 500px"
                :loading="loadingProcessList"
                show-search
                :filter-option="filterOption"
              >
                <a-select-option
                  v-for="doc in processedDocuments"
                  :key="doc.id"
                  :value="doc.id"
                  :disabled="doc.status !== 'parsed' && doc.status !== 'chunked' && doc.status !== 'error'"
                >
                  {{ doc.file_name }} ({{ formatFileSize(doc.file_size) }}) - {{ formatDateTime(doc.upload_time) }} - {{ getStatusText(doc.status) }}
                </a-select-option>
              </a-select>
              
              <a-button @click="loadProcessedDocuments" :loading="loadingProcessList">
                <template #icon><ReloadOutlined /></template>
                刷新
              </a-button>
            </div>
            
            <div style="display: flex; gap: 16px; align-items: center; flex-wrap: wrap; margin-bottom: 16px">
              <a-form-item label="实体和关系模板" style="margin-bottom: 0">
                <a-select
                  v-model:value="selectedTemplateId"
                  placeholder="选择模板（必选）"
                  style="width: 300px"
                  :loading="loadingTemplates"
                  show-search
                  :filter-option="filterTemplateOption"
                >
                  <a-select-option
                    v-for="template in templates"
                    :key="template.id"
                    :value="template.id"
                  >
                    {{ template.name }}
                    <a-tag v-if="template.is_default" color="blue" style="margin-left: 8px">默认</a-tag>
                    <a-tag v-if="template.is_llm_generated" color="orange" style="margin-left: 8px">LLM生成</a-tag>
                  </a-select-option>
                </a-select>
                <a-button type="link" @click="handleViewTemplate" style="margin-left: 8px" :disabled="!selectedTemplateId">
                  查看详情
                </a-button>
              </a-form-item>
            </div>
            
            <div style="display: flex; gap: 16px; align-items: center; flex-wrap: wrap">
              <span style="color: #666; font-size: 14px; margin-right: 8px">选择LLM:</span>
              <a-radio-group v-model:value="selectedProcessProvider">
                <a-radio value="local">本地大模型</a-radio>
              </a-radio-group>
              <a-switch
                v-model:checked="useThinking_process"
                style="margin-left: 24px"
                :disabled="selectedProcessProvider !== 'local'"
              >
                <template #checkedChildren>Thinking</template>
                <template #unCheckedChildren>Thinking</template>
              </a-switch>
              <span v-if="selectedProcessProvider === 'local'" style="color: #999; font-size: 12px; margin-left: 8px">启用Thinking模式</span>
              <span v-else style="color: #ccc; font-size: 12px; margin-left: 8px">（仅本地大模型支持）</span>
              
              <a-button
                type="primary"
                @click="handleProcess"
                :loading="processing"
                :disabled="!selectedProcessUploadId || !selectedTemplateId"
              >
                <template #icon><PlayCircleOutlined /></template>
                处理并保存到Neo4j
              </a-button>
            </div>
          </div>

          <!-- 处理结果 -->
          <a-card
            v-if="processResult"
            title="处理结果"
            style="margin-top: 16px"
          >
            <a-descriptions title="处理信息" :column="2" bordered>
              <a-descriptions-item label="文档ID">
                <code>{{ processResult.document_id }}</code>
              </a-descriptions-item>
              <a-descriptions-item label="文档名称">
                {{ processResult.document_name }}
              </a-descriptions-item>
              <a-descriptions-item label="版本">
                <a-tag color="blue">{{ processResult.version }}</a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="版本号">
                {{ processResult.version_number }}
          </a-descriptions-item>
        </a-descriptions>

            <a-divider />

            <a-descriptions title="Episode统计" :column="3" bordered style="margin-top: 16px">
              <a-descriptions-item label="总Episode数">
                <a-tag color="blue">{{ processResult.statistics.total_episodes || 0 }}</a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="章节Episode数">
                <a-tag color="green">{{ processResult.statistics.total_sections || 0 }}</a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="图片Episode数">
                <a-tag color="orange">{{ processResult.statistics.total_images || 0 }}</a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="表格Episode数">
                <a-tag color="purple">{{ processResult.statistics.total_tables || 0 }}</a-tag>
              </a-descriptions-item>
            </a-descriptions>
          </a-card>

          <!-- 空状态 -->
          <a-empty
            v-else-if="!processing && !loadingProcessList"
            description="请选择已解析的文档并点击'处理并保存到Neo4j'按钮"
          />
      </div>
      </a-tab-pane>

      <!-- Tab 6: 查看图谱 -->
      <a-tab-pane key="graph" tab="步骤6: 查看图谱">
        <div class="step-content">
        <a-alert
            message="查看图谱"
            description="选择已完成处理的文档，查看其知识图谱可视化"
          type="info"
            show-icon
            style="margin-bottom: 24px"
          />
          
          <!-- 文档选择 -->
          <div style="margin-bottom: 24px; display: flex; gap: 16px; align-items: center; flex-wrap: wrap">
            <a-select
              v-model:value="selectedGraphUploadId"
              placeholder="选择已完成的文档"
              style="width: 500px"
              :loading="loadingGraphList"
              show-search
              :filter-option="filterOption"
              @change="handleGraphDocumentChange"
            >
              <a-select-option
                v-for="doc in graphDocuments"
                :key="doc.id"
                :value="doc.id"
                :disabled="doc.status !== 'completed' || !doc.document_id"
              >
                {{ doc.file_name }} ({{ formatFileSize(doc.file_size) }}) - {{ formatDateTime(doc.upload_time) }} - {{ getStatusText(doc.status) }}
              </a-select-option>
            </a-select>
            
            <a-button @click="loadGraphDocuments" :loading="loadingGraphList">
              <template #icon><ReloadOutlined /></template>
              刷新
            </a-button>
      </div>

          <!-- 构建Community区域 -->
          <a-card 
            title="构建Community" 
            size="small" 
            style="margin-bottom: 16px"
          >
            <!-- 构建范围选择 -->
            <div style="margin-bottom: 16px">
              <span style="margin-right: 16px; font-weight: 500">构建范围：</span>
              <a-radio-group v-model:value="communityBuildScope">
                <a-radio value="current">当前文档</a-radio>
                <a-radio value="cross">跨文档</a-radio>
              </a-radio-group>
            </div>

            <!-- 跨文档选择器 -->
            <div v-if="communityBuildScope === 'cross'" style="margin-bottom: 16px">
              <a-select
                v-model:value="selectedCrossDocumentIds"
                mode="multiple"
                placeholder="选择多个已完成的文档（至少2个）"
                style="width: 100%"
                :loading="loadingGraphList"
                show-search
                :filter-option="filterOption"
              >
                <a-select-option
                  v-for="doc in graphDocuments"
                  :key="doc.id"
                  :value="doc.document_id"
                  :disabled="doc.status !== 'completed' || !doc.document_id"
                >
                  {{ doc.file_name }} ({{ doc.document_id }})
                </a-select-option>
              </a-select>
            </div>

            <!-- LLM选择和Thinking模式 -->
            <div style="margin-bottom: 16px">
              <a-space>
                <span style="color: #666; font-size: 14px; margin-right: 8px">选择LLM:</span>
                <a-radio-group v-model:value="selectedCommunityProvider">
                  <a-radio value="local">本地大模型</a-radio>
                </a-radio-group>
                <a-switch
                  v-model:checked="useThinking_community"
                  style="margin-left: 24px"
                  :disabled="selectedCommunityProvider !== 'local'"
                >
                  <template #checkedChildren>Thinking</template>
                  <template #unCheckedChildren>Thinking</template>
                </a-switch>
                <span v-if="selectedCommunityProvider === 'local'" style="color: #999; font-size: 12px; margin-left: 8px">启用Thinking模式</span>
                <span v-else style="color: #ccc; font-size: 12px; margin-left: 8px">（仅本地大模型支持）</span>
              </a-space>
            </div>

            <!-- 构建按钮 -->
            <div style="margin-bottom: 16px">
              <a-button
                type="primary"
                @click="handleBuildCommunities"
                :loading="buildingCommunities"
                :disabled="(communityBuildScope === 'current' && !selectedGraphUploadId) || 
                          (communityBuildScope === 'cross' && (!selectedCrossDocumentIds || selectedCrossDocumentIds.length < 2))"
              >
                <template #icon><PlayCircleOutlined /></template>
                构建Community
              </a-button>
            </div>

            <!-- 任务ID显示 -->
            <div v-if="communityTaskId" style="margin-top: 16px; margin-bottom: 16px">
              <a-alert
                type="info"
                :message="`任务已提交，正在后台处理中... 任务ID: ${communityTaskId}`"
                show-icon
              >
                <template #action>
                  <a-button type="link" size="small" @click="router.push('/tasks')">
                    前往任务管理
                  </a-button>
                </template>
              </a-alert>
            </div>

            <!-- 构建结果（保留用于兼容，但异步任务不会直接显示结果） -->
            <div v-if="communitiesResult" style="margin-top: 16px">
              <a-descriptions title="Community统计" :column="2" bordered>
                <a-descriptions-item label="Community数量">
                  <a-tag color="blue">{{ communitiesResult.statistics?.total_communities || 0 }}</a-tag>
                </a-descriptions-item>
                <a-descriptions-item label="包含实体总数">
                  <a-tag color="green">{{ communitiesResult.statistics?.total_entities || 0 }}</a-tag>
                </a-descriptions-item>
              </a-descriptions>

              <!-- Community列表 -->
              <div style="margin-top: 16px">
                <h4 style="margin-bottom: 12px">Community列表</h4>
          <a-list
                  :data-source="communitiesResult.communities || []"
                  :bordered="true"
          >
            <template #renderItem="{ item }">
              <a-list-item>
                <a-list-item-meta>
                  <template #title>
                    <a-space>
                            <span style="font-weight: 500">{{ item.name }}</span>
                            <a-tag color="blue">{{ item.entity_count }} 个实体</a-tag>
                    </a-space>
                  </template>
                  <template #description>
                          <div>
                            <div style="margin-bottom: 8px; color: #666">{{ item.summary || '无摘要' }}</div>
                            <div v-if="item.group_ids && item.group_ids.length > 0" style="font-size: 12px; color: #999">
                              来源文档: {{ item.group_ids.join(', ') }}
                      </div>
                    </div>
                  </template>
                </a-list-item-meta>
              </a-list-item>
            </template>
          </a-list>
              </div>
            </div>
          </a-card>

          <!-- 筛选控件 -->
          <a-card 
            v-if="selectedGraphUploadId && rawGraphData" 
            title="图谱筛选" 
            size="small" 
            style="margin-bottom: 16px"
          >
            <a-row :gutter="[16, 16]">
              <!-- Episode节点筛选 -->
              <a-col :span="8">
                <div style="border: 1px solid #f0f0f0; padding: 12px; border-radius: 4px;">
                  <a-checkbox 
                    v-model:checked="graphFilterConfig.showEpisodes"
                    style="font-weight: 500; margin-bottom: 8px;"
                  >
                    Episode节点
                  </a-checkbox>
                  <div style="margin-left: 24px; margin-top: 8px;">
                    <a-space direction="vertical" size="small" style="width: 100%">
                      <a-checkbox 
                        v-model:checked="graphFilterConfig.showEpisodeTypes.document"
                        :disabled="!graphFilterConfig.showEpisodes"
                      >
                        文档级Episode
                      </a-checkbox>
                      <a-checkbox 
                        v-model:checked="graphFilterConfig.showEpisodeTypes.section"
                        :disabled="!graphFilterConfig.showEpisodes"
                      >
                        章节级Episode
                      </a-checkbox>
                      <a-checkbox 
                        v-model:checked="graphFilterConfig.showEpisodeTypes.image"
                        :disabled="!graphFilterConfig.showEpisodes"
                      >
                        图片Episode
                      </a-checkbox>
                      <a-checkbox 
                        v-model:checked="graphFilterConfig.showEpisodeTypes.table"
                        :disabled="!graphFilterConfig.showEpisodes"
                      >
                        表格Episode
                      </a-checkbox>
          </a-space>
        </div>
                </div>
              </a-col>

              <!-- Entity节点筛选 -->
              <a-col :span="8">
                <div style="border: 1px solid #f0f0f0; padding: 12px; border-radius: 4px;">
                  <a-checkbox 
                    v-model:checked="graphFilterConfig.showEntities"
                    style="font-weight: 500; margin-bottom: 8px;"
                  >
                    Entity节点
                  </a-checkbox>
                  <div style="margin-left: 24px; margin-top: 8px;">
                    <a-space direction="vertical" size="small" style="width: 100%">
                      <a-checkbox 
                        v-model:checked="graphFilterConfig.showEntityTypes.Person"
                        :disabled="!graphFilterConfig.showEntities"
                      >
                        Person
                      </a-checkbox>
                      <a-checkbox 
                        v-model:checked="graphFilterConfig.showEntityTypes.Organization"
                        :disabled="!graphFilterConfig.showEntities"
    >
                        Organization
                      </a-checkbox>
                      <a-checkbox 
                        v-model:checked="graphFilterConfig.showEntityTypes.Concept"
                        :disabled="!graphFilterConfig.showEntities"
                      >
                        Concept
                      </a-checkbox>
                      <a-checkbox 
                        v-model:checked="graphFilterConfig.showEntityTypes.Requirement"
                        :disabled="!graphFilterConfig.showEntities"
                      >
                        Requirement
                      </a-checkbox>
                      <a-checkbox 
                        v-model:checked="graphFilterConfig.showEntityTypes.Feature"
                        :disabled="!graphFilterConfig.showEntities"
                      >
                        Feature
                      </a-checkbox>
                      <a-checkbox 
                        v-model:checked="graphFilterConfig.showEntityTypes.Entity"
                        :disabled="!graphFilterConfig.showEntities"
            >
                        其他Entity
                      </a-checkbox>
                    </a-space>
                  </div>
                </div>
              </a-col>

              <!-- Community节点筛选 -->
              <a-col :span="8">
                <div style="border: 1px solid #f0f0f0; padding: 12px; border-radius: 4px;">
                  <a-checkbox 
                    v-model:checked="graphFilterConfig.showCommunities"
                    style="font-weight: 500; margin-bottom: 8px;"
                  >
                    Community节点
                  </a-checkbox>
                </div>
              </a-col>
            </a-row>
            
            <a-row :gutter="[16, 16]" style="margin-top: 16px">
              <!-- 关系边筛选 -->
              <a-col :span="8">
                <div style="border: 1px solid #f0f0f0; padding: 12px; border-radius: 4px;">
                  <a-checkbox 
                    v-model:checked="graphFilterConfig.showRelations"
                    style="font-weight: 500; margin-bottom: 8px;"
                  >
                    关系边
                  </a-checkbox>
                  <div style="margin-left: 24px; margin-top: 8px;">
                    <a-space direction="vertical" size="small" style="width: 100%">
                      <a-checkbox 
                        v-model:checked="graphFilterConfig.showRelationTypes.RELATES_TO"
                        :disabled="!graphFilterConfig.showRelations"
                      >
                        RELATES_TO
                      </a-checkbox>
                      <a-checkbox 
                        v-model:checked="graphFilterConfig.showRelationTypes.MENTIONS"
                        :disabled="!graphFilterConfig.showRelations"
                      >
                        MENTIONS
                      </a-checkbox>
                      <a-checkbox 
                        v-model:checked="graphFilterConfig.showRelationTypes.CONTAINS"
                        :disabled="!graphFilterConfig.showRelations"
                      >
                        CONTAINS
                      </a-checkbox>
                      <a-checkbox 
                        v-model:checked="graphFilterConfig.showRelationTypes.HAS_MEMBER"
                        :disabled="!graphFilterConfig.showRelations"
                      >
                        HAS_MEMBER
                      </a-checkbox>
                    </a-space>
                  </div>
                </div>
              </a-col>
            </a-row>
            
            <!-- 筛选统计信息 -->
            <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #f0f0f0; color: #666; font-size: 12px;">
              <a-space>
                <span>显示节点: {{ currentGraphData?.nodes?.length || 0 }} / {{ rawGraphData?.nodes?.length || 0 }}</span>
                <span>显示关系: {{ currentGraphData?.edges?.length || 0 }} / {{ rawGraphData?.edges?.length || 0 }}</span>
              </a-space>
            </div>
          </a-card>

          <!-- 图谱可视化 -->
          <div v-if="selectedGraphUploadId && currentGraphData" style="height: calc(100vh - 500px); border: 1px solid #f0f0f0; border-radius: 4px; position: relative;">
            <GraphVisualization 
              :data="currentGraphData" 
              @nodeClick="handleGraphNodeClick"
              @edgeClick="handleGraphEdgeClick"
            />
          </div>
          
          <a-spin v-else-if="loadingGraph" style="width: 100%; height: calc(100vh - 500px); display: flex; align-items: center; justify-content: center;" />
          
          <a-empty
            v-else-if="!loadingGraph && !loadingGraphList"
            description="请选择已完成的文档查看知识图谱"
            style="height: calc(100vh - 500px); display: flex; align-items: center; justify-content: center;"
          />
        </div>
      </a-tab-pane>
    </a-tabs>

    <!-- 查看解析结果模态框（必须放在 a-tabs 外部） -->
    <a-modal
      v-model:open="parsedContentModalVisible"
      :title="`查看解析结果 - ${parsedContentModalData?.file_name || ''}`"
      width="1200px"
      :footer="null"
      :maskClosable="false"
    >
      <a-spin :spinning="parsedContentLoading">
        <a-tabs v-model:activeKey="parsedContentTab" v-if="!parsedContentLoading">
          <!-- Tab 1: 完整对应文档 -->
          <a-tab-pane key="parsed" tab="完整对应文档">
            <div v-if="parsedContentText">
              <div style="display: flex; justify-content: flex-end; margin-bottom: 8px;">
                <a-button size="small" type="primary" ghost @click="downloadFile('parsed')">
                  <template #icon><DownloadOutlined /></template>
                  下载
                </a-button>
        </div>
              <div 
                style="background: #f5f5f5; padding: 16px; border-radius: 4px; max-height: calc(100vh - 340px); overflow-y: auto; font-family: 'Microsoft YaHei', sans-serif; font-size: 14px; line-height: 1.8;"
                v-html="formatMarkdown(parsedContentText, `upload_${parsedContentModalData?.id}`, parsedContentModalData?.id)"
              ></div>
      </div>
            <a-empty v-else description="完整对应文档不可用" />
          </a-tab-pane>
          
          <!-- Tab 2: 总结文档 -->
          <a-tab-pane key="summary" tab="总结文档">
            <div v-if="summaryContentText">
              <div style="display: flex; justify-content: flex-end; margin-bottom: 8px;">
                <a-button size="small" type="primary" ghost @click="downloadFile('summary')">
                  <template #icon><DownloadOutlined /></template>
                  下载
                </a-button>
              </div>
              <div 
                style="background: #f5f5f5; padding: 16px; border-radius: 4px; max-height: calc(100vh - 340px); overflow-y: auto; font-family: 'Microsoft YaHei', sans-serif; font-size: 14px; line-height: 1.8;"
                v-html="formatMarkdown(summaryContentText, `upload_${parsedContentModalData?.id}`, parsedContentModalData?.id)"
              ></div>
            </div>
            <a-empty v-else description="总结文档不可用" />
          </a-tab-pane>
          
          <!-- Tab 3: 结构化数据 -->
          <a-tab-pane key="structured" tab="结构化数据">
            <div v-if="structuredContentText">
              <div style="display: flex; justify-content: flex-end; margin-bottom: 8px;">
                <a-button size="small" type="primary" ghost @click="downloadFile('structured')">
                  <template #icon><DownloadOutlined /></template>
                  下载
                </a-button>
              </div>
              <pre 
                style="background: #1e1e1e; color: #d4d4d4; padding: 16px; border-radius: 4px; max-height: calc(100vh - 340px); overflow: auto; font-family: 'Consolas', 'Monaco', monospace; font-size: 12px; line-height: 1.5; white-space: pre-wrap; word-wrap: break-word;"
              >{{ structuredContentText }}</pre>
            </div>
            <a-empty v-else description="结构化数据不可用" />
          </a-tab-pane>
          
          <!-- Tab 4: 分块结果 -->
          <a-tab-pane key="chunks" tab="分块结果">
            <div v-if="chunksContentData">
              <div style="display: flex; justify-content: flex-end; margin-bottom: 8px;">
                <a-button size="small" type="primary" ghost @click="downloadFile('chunks')">
                  <template #icon><DownloadOutlined /></template>
                  下载
                </a-button>
              </div>
              <!-- 分块统计信息 -->
              <a-descriptions title="分块信息" :column="4" bordered style="margin-bottom: 16px">
                <a-descriptions-item label="分块策略">
                  <a-tag color="blue">{{ getStrategyName(chunksContentData.strategy) }}</a-tag>
                </a-descriptions-item>
                <a-descriptions-item label="总块数">
                  <a-tag color="green">{{ chunksContentData.total_chunks }}</a-tag>
                </a-descriptions-item>
                <a-descriptions-item label="Max Tokens">
                  {{ chunksContentData.max_tokens }}
                </a-descriptions-item>
                <a-descriptions-item label="创建时间">
                  {{ chunksContentData.created_at ? new Date(chunksContentData.created_at).toLocaleString() : '-' }}
                </a-descriptions-item>
              </a-descriptions>
              
              <!-- 分块列表 -->
              <a-table
                :dataSource="chunksContentData.chunks || []"
                :columns="chunksColumns"
                :pagination="false"
                size="small"
                :scroll="{ y: 'calc(100vh - 500px)' }"
                rowKey="chunk_id"
              >
                <template #bodyCell="{ column, record }">
                  <template v-if="column.key === 'content'">
                    <a-tooltip :title="record.content">
                      <span style="max-width: 400px; display: inline-block; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                        {{ record.content?.substring(0, 100) }}{{ record.content?.length > 100 ? '...' : '' }}
                      </span>
                    </a-tooltip>
                  </template>
                </template>
              </a-table>
            </div>
            <a-empty v-else description="分块结果不可用（请先执行步骤4分块）" />
          </a-tab-pane>
        </a-tabs>
        <a-empty v-else description="正在加载解析结果..." />
      </a-spin>
    </a-modal>

    <!-- 节点详情抽屉 -->
    <a-drawer
      v-model:open="nodeDetailVisible"
      title="节点属性"
      placement="right"
      :width="400"
      @close="selectedGraphNode = null"
    >
      <div v-if="selectedGraphNode" style="padding: 16px 0;">
        <a-descriptions :column="1" bordered>
          <a-descriptions-item label="ID">{{ selectedGraphNode.id }}</a-descriptions-item>
          <a-descriptions-item label="名称">{{ selectedGraphNode.properties?.name || selectedGraphNode.name || '-' }}</a-descriptions-item>
          <a-descriptions-item label="类型">
            <a-tag>{{ selectedGraphNode.labels?.[0] || selectedGraphNode.type || 'Entity' }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="所有标签">
            <a-space>
              <a-tag v-for="label in (selectedGraphNode.labels || [selectedGraphNode.type].filter(Boolean))" :key="label">{{ label }}</a-tag>
            </a-space>
          </a-descriptions-item>
          <a-descriptions-item label="创建时间" v-if="selectedGraphNode.properties?.created_at">
            {{ new Date(selectedGraphNode.properties.created_at).toLocaleString('zh-CN') }}
          </a-descriptions-item>
          <a-descriptions-item label="其他属性" v-if="hasOtherNodeProperties">
            <div style="max-height: 300px; overflow-y: auto;">
              <a-descriptions :column="1" size="small" bordered>
                <a-descriptions-item 
                  v-for="(value, key) in otherNodeProperties" 
                  :key="key"
                  :label="key"
                >
                  <pre style="margin: 0; white-space: pre-wrap; word-break: break-all; font-size: 12px;">{{ formatPropertyValue(value) }}</pre>
                </a-descriptions-item>
              </a-descriptions>
            </div>
          </a-descriptions-item>
        </a-descriptions>
      </div>
    </a-drawer>
  </a-card>
</template>

<script setup>
import { ref, computed, onMounted, watch, h } from 'vue'
import { useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import { UploadOutlined, ReloadOutlined, PlayCircleOutlined, FileTextOutlined, EditOutlined, QuestionCircleOutlined, DownloadOutlined, EyeOutlined } from '@ant-design/icons-vue'
import { uploadDocument, getDocumentUploadList, deleteDocumentUpload, parseDocument, processDocument, generateVersion, updateVersion, splitDocument, getParsedContent, getSummaryContent, getStructuredContent, getChunks, buildCommunities, buildCommunitiesAsync, getGroupIds } from '../api/documentUpload'
import { submitTask, getTask } from '../api/taskManagement'
import { getDocumentGraph } from '../api/wordDocument'
import { getTemplates, getTemplate } from '../api/templateManagement'
import GraphVisualization from '../components/GraphVisualization.vue'

const activeTab = ref('upload')
const selectedProvider = ref('qianwen')

// 步骤1：文档上传与验证
const uploadFileList = ref([])
const uploadProcessing = ref(false)
const documents = ref([])
const loading = ref(false)
const searchKeyword = ref('')
const filterStatus = ref(null)

// 步骤2：文档解析
const uploadedDocuments = ref([])
const loadingUploadList = ref(false)
const selectedUploadId = ref(null)
const parsing = ref(false)
const parseResult = ref(null)
const contentViewTab = ref('original') // 内容查看Tab：'original' 原始文档，'parsed' 完整对应文档，'summary' 总结文档，'structured' 结构化数据
const wordDocumentHtml = ref(null)
const loadingWordDocument = ref(false)

// 步骤3：版本管理
const versionDocuments = ref([])
const loadingVersionList = ref(false)
const selectedVersionUploadId = ref(null)
const customGroupId = ref('') // 用户自定义的 Group ID
const generatingVersion = ref(false)
const versionResult = ref(null)
const editingVersion = ref(false) // 是否正在编辑版本信息
const editingVersionData = ref({ version: '', version_number: 1, group_id: '' }) // 编辑中的数据
const savingVersion = ref(false) // 是否正在保存
const groupIdValidationStatus = ref('') // Group ID 验证状态
const groupIdValidationError = ref('') // Group ID 验证错误信息
const groupIdOptions = ref([]) // Group ID 下拉选项列表
const loadingGroupIds = ref(false) // 加载 Group ID 列表的状态
const groupIdSearchValue = ref('') // Group ID 搜索值

// 步骤4：章节分块
const splitDocuments = ref([])
const loadingSplitList = ref(false)
const selectedSplitUploadId = ref(null)
const splitStrategy = ref('level_1')  // 分块策略：level_1, level_2, fixed_token, no_split
const maxTokensPerSection = ref(8000)
const splitting = ref(false)
const splitResult = ref(null)

// 步骤5：创建Episode并保存到Neo4j
const processedDocuments = ref([])
const loadingProcessList = ref(false)
const selectedProcessUploadId = ref(null)
const selectedProcessProvider = ref('local')
const useThinking_process = ref(false)
const processing = ref(false)
const processResult = ref(null)
const templates = ref([])
const loadingTemplates = ref(false)
const selectedTemplateId = ref(null)

// 步骤6：查看图谱
const graphDocuments = ref([])
const loadingGraphList = ref(false)
const selectedGraphUploadId = ref(null)
const loadingGraph = ref(false)
const currentGraphData = ref(null)
const rawGraphData = ref(null) // 原始图谱数据（未筛选）
const selectedGraphNode = ref(null)
const nodeDetailVisible = ref(false)

// 步骤6：构建Community
const communityBuildScope = ref('current') // 'current' 或 'cross'
const selectedCrossDocumentIds = ref([]) // 跨文档时选择的group_id列表
const selectedCommunityProvider = ref('local') // LLM提供商
const useThinking_community = ref(false) // 是否启用Thinking模式
const buildingCommunities = ref(false)
const communityTaskId = ref(null) // 构建Community任务ID
const communitiesResult = ref(null)

// 步骤6：筛选配置
const graphFilterConfig = ref({
  // Episode节点筛选
  showEpisodes: true,
  showEpisodeTypes: {
    document: true,  // 文档级Episode
    section: true,   // 章节级Episode
    image: true,     // 图片Episode
    table: true      // 表格Episode
  },
  // Entity节点筛选
  showEntities: true,
  showEntityTypes: {
    Person: true,
    Organization: true,
    Location: true,
    Concept: true,
    Event: true,
    Product: true,
    Technology: true,
    Document: true,
    Requirement: true,
    Feature: true,
    Module: true,
    Entity: true  // 其他Entity类型
  },
  // Community节点筛选
  showCommunities: true,
  // 关系边筛选
  showRelations: true,
  showRelationTypes: {
    RELATES_TO: true,
    MENTIONS: true,
    CONTAINS: true,
    HAS_MEMBER: true
  }
})

// 步骤6：展开/折叠细分类别
const filterExpanded = ref({
  episodes: false,
  entities: false,
  relations: false
})

// 查看解析结果模态框
const parsedContentModalVisible = ref(false)
const parsedContentModalData = ref(null)
const parsedContentLoading = ref(false)
const parsedContentTab = ref('parsed')
const parsedContentText = ref('')
const summaryContentText = ref('')
const structuredContentText = ref('')
const chunksContentData = ref(null)

// 分块结果列表表头
const chunksColumns = [
  { title: '块ID', dataIndex: 'chunk_id', key: 'chunk_id', width: 100 },
  { title: '标题', dataIndex: 'title', key: 'title', width: 200, ellipsis: true },
  { title: '级别', dataIndex: 'level', key: 'level', width: 60, align: 'center' },
  { title: 'Tokens', dataIndex: 'token_count', key: 'token_count', width: 80, align: 'right' },
  { title: '内容预览', dataIndex: 'content', key: 'content' }
]

// 获取策略名称
const getStrategyName = (strategy) => {
  const names = {
    'level_1': '按一级标题',
    'level_2': '按二级标题',
    'level_3': '按三级标题',
    'level_4': '按四级标题',
    'level_5': '按五级标题',
    'fixed_token': '按固定Token',
    'no_split': '不分块'
  }
  return names[strategy] || strategy
}

// 下载文件
const downloadFile = (type) => {
  if (!parsedContentModalData.value) return
  
  // 获取原文件名（去掉扩展名）
  const originalFileName = parsedContentModalData.value.file_name?.replace(/\.[^/.]+$/, '') || 'document'
  
  let content = ''
  let fileName = ''
  let mimeType = ''
  
  switch (type) {
    case 'parsed':
      content = parsedContentText.value
      fileName = `${originalFileName}_完整对应文档.md`
      mimeType = 'text/markdown;charset=utf-8'
      break
    case 'summary':
      content = summaryContentText.value
      fileName = `${originalFileName}_总结文档.md`
      mimeType = 'text/markdown;charset=utf-8'
      break
    case 'structured':
      content = structuredContentText.value
      fileName = `${originalFileName}_结构化数据.json`
      mimeType = 'application/json;charset=utf-8'
      break
    case 'chunks':
      content = JSON.stringify(chunksContentData.value, null, 2)
      fileName = `${originalFileName}_分块结果.json`
      mimeType = 'application/json;charset=utf-8'
      break
    default:
      return
  }
  
  if (!content) {
    message.warning('没有可下载的内容')
    return
  }
  
  // 创建 Blob 并下载
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = fileName
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
  
  message.success(`已下载: ${fileName}`)
}

// 下载步骤2解析的结构化数据
const downloadParseStructured = () => {
  if (!parseResult.value || !parseResult.value.structured_content) {
    message.warning('没有可下载的内容')
    return
  }
  
  const originalFileName = parseResult.value.file_name?.replace(/\.[^/.]+$/, '') || 'document'
  const content = JSON.stringify(parseResult.value.structured_content, null, 2)
  const fileName = `${originalFileName}_结构化数据.json`
  const mimeType = 'application/json;charset=utf-8'
  
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = fileName
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
  
  message.success(`已下载: ${fileName}`)
}

// 分页
const pagination = ref({
  current: 1,
  pageSize: 10,
  total: 0,
  showTotal: (total) => `共 ${total} 条`,
  showSizeChanger: true,
  pageSizeOptions: ['10', '20', '50', '100']
})

// 表格列定义
const columns = [
  {
    title: '文件名',
    dataIndex: 'file_name',
    key: 'file_name',
    ellipsis: true
  },
  {
    title: '文件大小',
    dataIndex: 'file_size',
    key: 'file_size',
    width: 120
  },
  {
    title: '上传时间',
    dataIndex: 'upload_time',
    key: 'upload_time',
    width: 180
  },
  {
    title: '验证状态',
    dataIndex: 'status',
    key: 'status',
    width: 120
  },
  {
    title: '操作',
    key: 'action',
    width: 250,
    fixed: 'right'
  }
]

// 步骤状态控制
const canProceedToStep2 = computed(() => {
  // 直接允许进入步骤2，让用户选择文件进行解析
  // 或者检查是否有已上传的文件（状态为validated）
  return true  // 直接允许，不限制
})

const canProceedToStep3 = computed(() => {
  // 检查是否有已解析的文档（状态为parsed）
  // 同时检查documents（步骤1使用的）、uploadedDocuments（步骤2使用的）和processedDocuments（步骤5使用的）
  const hasParsedInDocuments = documents.value.some(doc => doc.status === 'parsed')
  const hasParsedInUploaded = uploadedDocuments.value.some(doc => doc.status === 'parsed')
  const hasParsedInProcessed = processedDocuments.value.some(doc => doc.status === 'parsed')
  return hasParsedInDocuments || hasParsedInUploaded || hasParsedInProcessed
})

const canProceedToStep4 = computed(() => {
  // 检查是否有已解析的文档（状态为parsed）
  // 同时检查documents（步骤1使用的）、uploadedDocuments（步骤2使用的）和processedDocuments（步骤5使用的）
  const hasParsedInDocuments = documents.value.some(doc => doc.status === 'parsed')
  const hasParsedInUploaded = uploadedDocuments.value.some(doc => doc.status === 'parsed')
  const hasParsedInProcessed = processedDocuments.value.some(doc => doc.status === 'parsed')
  return hasParsedInDocuments || hasParsedInUploaded || hasParsedInProcessed
})

const canProceedToStep5 = computed(() => {
  // 检查是否有已解析的文档（状态为parsed）
  // 同时检查documents（步骤1使用的）、uploadedDocuments（步骤2使用的）和processedDocuments（步骤5使用的）
  const hasParsedInDocuments = documents.value.some(doc => doc.status === 'parsed')
  const hasParsedInUploaded = uploadedDocuments.value.some(doc => doc.status === 'parsed')
  const hasParsedInProcessed = processedDocuments.value.some(doc => doc.status === 'parsed')
  return hasParsedInDocuments || hasParsedInUploaded || hasParsedInProcessed
})

// 加载文档列表
const loadDocumentList = async () => {
  loading.value = true
  try {
    const response = await getDocumentUploadList(
      pagination.value.current,
      pagination.value.pageSize,
      searchKeyword.value || null,
      filterStatus.value || null
    )
    documents.value = response.documents || []
    pagination.value.total = response.total || 0
  } catch (error) {
    console.error('加载文档列表失败:', error)
    message.error(`加载文档列表失败: ${error.message || '未知错误'}`)
  } finally {
    loading.value = false
  }
}

// 文件上传处理
const handleUpload = async (file) => {
  uploadFileList.value = [file]
  uploadProcessing.value = true

  try {
    // 前端验证文件格式
    const fileName = file.name
    const fileExtension = fileName.substring(fileName.lastIndexOf('.')).toLowerCase()
    const formatValid = fileExtension === '.docx' || fileExtension === '.doc'

          if (!formatValid) {
            message.error('文件格式验证失败：只支持 .docx 格式，暂不支持 .doc 格式')
            uploadProcessing.value = false
            return false
          }

    // 验证文件大小（50MB限制）
    const maxSize = 50 * 1024 * 1024 // 50MB
    if (file.size > maxSize) {
      message.error('文件大小超过限制：最大支持 50MB')
      uploadProcessing.value = false
      return false
    }

    // 调用上传API
    message.info('正在上传文件并验证...')
    const response = await uploadDocument(file)
    
    message.success('文件上传并验证成功！')
    uploadFileList.value = []
    
    // 刷新列表
    await loadDocumentList()
  } catch (error) {
    console.error('上传验证失败:', error)
    message.error(`上传验证失败: ${error.message || '未知错误'}`)
  } finally {
    uploadProcessing.value = false
  }

  return false // 阻止自动上传
}

// 搜索
const handleSearch = () => {
  pagination.value.current = 1
  loadDocumentList()
}

// 筛选
const handleFilter = () => {
  pagination.value.current = 1
  loadDocumentList()
}

// 删除文档
const handleDelete = (record) => {
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除文档 "${record.file_name}" 吗？`,
    onOk: async () => {
      try {
        await deleteDocumentUpload(record.id)
        message.success('删除成功')
        loadDocumentList()
      } catch (error) {
        message.error(`删除失败: ${error.message || '未知错误'}`)
      }
    }
  })
}

// 重新上传
const handleReupload = (record) => {
  message.info('重新上传功能：请使用上传按钮重新选择文件')
}

// 表格变化处理
const handleTableChange = (pag) => {
  pagination.value.current = pag.current
  pagination.value.pageSize = pag.pageSize
  loadDocumentList()
}

// 格式化文件大小
const formatFileSize = (bytes) => {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

// 格式化日期时间
const formatDateTime = (dateTimeStr) => {
  if (!dateTimeStr) return '-'
  try {
    const date = new Date(dateTimeStr)
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  } catch (e) {
    return dateTimeStr
  }
}

// 获取状态颜色
const getStatusColor = (status) => {
  const colorMap = {
    'validated': 'blue',
    'parsing': 'processing',
    'parsed': 'cyan',
    'chunking': 'processing',
    'chunked': 'green',
    'completed': 'success',
    'error': 'error'
  }
  return colorMap[status] || 'default'
}

// 获取状态文本
const getStatusText = (status) => {
  const textMap = {
    'validated': '已验证',
    'parsing': '解析中',
    'parsed': '已解析',
    'chunking': '分块中',
    'chunked': '已分块',
    'completed': '已完成',
    'error': '错误'
  }
  return textMap[status] || status
}

// 加载已上传的文件列表（用于步骤2选择）
// 显示所有未删除的文件，不限制状态
const loadUploadedDocuments = async () => {
  console.log('[loadUploadedDocuments] 开始加载文件列表...')
  loadingUploadList.value = true
  try {
    // 不传status参数，获取所有文件（包括validated、parsed、chunked等状态）
    console.log('[loadUploadedDocuments] 调用API: getDocumentUploadList(1, 100, null, null)')
    const response = await getDocumentUploadList(1, 100, null, null)
    console.log('[loadUploadedDocuments] API响应:', JSON.stringify(response, null, 2))
    uploadedDocuments.value = response.documents || []
    console.log('[loadUploadedDocuments] 已设置 uploadedDocuments.value，数量:', uploadedDocuments.value.length)
    console.log('[loadUploadedDocuments] uploadedDocuments.value 内容:', uploadedDocuments.value)
    if (uploadedDocuments.value.length === 0) {
      console.warn('[loadUploadedDocuments] ⚠️ 文件列表为空！')
    } else {
      console.log('[loadUploadedDocuments] ✅ 文件列表加载成功，共', uploadedDocuments.value.length, '个文件')
    }
  } catch (error) {
    console.error('[loadUploadedDocuments] ❌ 加载失败:', error)
    console.error('[loadUploadedDocuments] 错误详情:', error.response || error.message)
    message.error(`加载文件列表失败: ${error.message || '未知错误'}`)
  } finally {
    loadingUploadList.value = false
    console.log('[loadUploadedDocuments] 加载完成，loadingUploadList.value = false')
  }
}

// 文件选择处理
const handleFileSelect = (value) => {
  selectedUploadId.value = value
  parseResult.value = null
  wordDocumentHtml.value = null // 清空之前的Word文档HTML
  contentViewTab.value = 'original' // 重置到原始文档Tab
}

// 实时解析
const handleParse = async () => {
  if (!selectedUploadId.value) {
    message.warning('请先选择文件')
    return
  }

  parsing.value = true
  parseResult.value = null
  wordDocumentHtml.value = null // 清空之前的Word文档HTML
  contentViewTab.value = 'original' // 重置到原始文档Tab

  try {
    message.info('开始解析文档...')
    const response = await parseDocument(selectedUploadId.value, 8000)
    parseResult.value = response
    message.success('文档解析完成！')
    
    // 更新uploadedDocuments中对应文档的状态为parsed
    const docIndex = uploadedDocuments.value.findIndex(doc => doc.id === selectedUploadId.value)
    if (docIndex !== -1) {
      uploadedDocuments.value[docIndex].status = 'parsed'
      console.log('[handleParse] 已更新文档状态为parsed:', selectedUploadId.value)
    }
    
    // 同时更新processedDocuments
    const processedIndex = processedDocuments.value.findIndex(doc => doc.id === selectedUploadId.value)
    if (processedIndex !== -1) {
      processedDocuments.value[processedIndex].status = 'parsed'
    } else {
      // 如果processedDocuments中没有，则添加
      const doc = uploadedDocuments.value.find(doc => doc.id === selectedUploadId.value)
      if (doc) {
        processedDocuments.value.push({ ...doc, status: 'parsed' })
      }
    }
  } catch (error) {
    console.error('解析文档失败:', error)
    message.error(`解析失败: ${error.message || '未知错误'}`)
  } finally {
    parsing.value = false
  }
}

// 步骤3：加载已解析的文档列表（用于版本管理）
const loadVersionDocuments = async () => {
  loadingVersionList.value = true
  try {
    console.log('[loadVersionDocuments] 开始加载文档列表...')
    const response = await getDocumentUploadList(1, 100, null, null)
    versionDocuments.value = response.documents || []
    console.log('[loadVersionDocuments] 文档列表加载完成，数量:', versionDocuments.value.length)
      } catch (error) {
    console.error('加载文档列表失败:', error)
    message.error(`加载文档列表失败: ${error.message || '未知错误'}`)
  } finally {
    loadingVersionList.value = false
  }
}

// 步骤3：加载 Group ID 列表
const loadGroupIds = async (searchValue = '') => {
  loadingGroupIds.value = true
  try {
    const groupIds = await getGroupIds(searchValue || null, 50)
    // 转换为 a-auto-complete 需要的格式
    groupIdOptions.value = (groupIds || []).map(id => ({
      value: id,
      label: id
    }))
    console.log('[loadGroupIds] 加载完成，数量:', groupIdOptions.value.length)
  } catch (error) {
    console.error('加载 Group ID 列表失败:', error)
    // 不显示错误消息，避免干扰用户输入
    groupIdOptions.value = []
  } finally {
    loadingGroupIds.value = false
  }
}

// 步骤3：Group ID 搜索处理（防抖）
let groupIdSearchTimer = null
const handleGroupIdSearch = (value) => {
  groupIdSearchValue.value = value
  // 防抖处理，300ms 后执行搜索
  if (groupIdSearchTimer) {
    clearTimeout(groupIdSearchTimer)
  }
  groupIdSearchTimer = setTimeout(() => {
    loadGroupIds(value)
  }, 300)
}

// 步骤3：文档选择变化处理
const handleVersionDocumentChange = () => {
  // 切换文档时清空自定义 Group ID 和版本结果
  customGroupId.value = ''
  versionResult.value = null
  editingVersion.value = false
}

// 步骤3：验证 Group ID 格式
const validateGroupId = (groupId) => {
  if (!groupId || groupId.trim() === '') {
    groupIdValidationStatus.value = ''
    groupIdValidationError.value = ''
    return true
  }
  
  // Graphiti 要求：只能包含字母数字、破折号、下划线
  const pattern = /^[a-zA-Z0-9\-_]+$/
  if (!pattern.test(groupId)) {
    groupIdValidationStatus.value = 'error'
    groupIdValidationError.value = 'Group ID 只能包含字母、数字、破折号(-)和下划线(_)'
    return false
}

  groupIdValidationStatus.value = 'success'
  groupIdValidationError.value = ''
  return true
}

// 步骤3：开始编辑版本信息
const startEditVersion = () => {
  if (!versionResult.value) return
  
  editingVersion.value = true
  editingVersionData.value = {
    version: versionResult.value.version,
    version_number: versionResult.value.version_number,
    group_id: versionResult.value.group_id
  }
  groupIdValidationStatus.value = ''
  groupIdValidationError.value = ''
}

// 步骤3：取消编辑
const cancelEditVersion = () => {
  editingVersion.value = false
  editingVersionData.value = { version: '', version_number: 1, group_id: '' }
  groupIdValidationStatus.value = ''
  groupIdValidationError.value = ''
}

// 步骤3：保存版本信息
const saveVersion = async () => {
  if (!versionResult.value) return
  
  // 验证 Group ID
  if (!validateGroupId(editingVersionData.value.group_id)) {
    message.warning('请修正 Group ID 格式')
    return
  }
  
  // 验证版本号
  if (!editingVersionData.value.version || editingVersionData.value.version.trim() === '') {
    message.warning('请输入版本号')
    return
  }
  
  if (!editingVersionData.value.version_number || editingVersionData.value.version_number < 1) {
    message.warning('版本号必须大于0')
    return
  }
  
  savingVersion.value = true
  
  try {
    message.info('正在保存版本信息...')
    const response = await updateVersion(
      versionResult.value.upload_id,
      editingVersionData.value.version,
      editingVersionData.value.version_number,
      editingVersionData.value.group_id
    )
    
    // 更新本地数据
    versionResult.value = {
      ...versionResult.value,
      version: response.version,
      version_number: response.version_number,
      group_id: response.group_id
    }
    
    editingVersion.value = false
    message.success('版本信息保存成功！')
  } catch (error) {
    console.error('保存版本信息失败:', error)
    message.error(`保存失败: ${error.message || '未知错误'}`)
  } finally {
    savingVersion.value = false
  }
}

// 步骤3：生成版本信息
const handleGenerateVersion = async () => {
  if (!selectedVersionUploadId.value) {
    message.warning('请先选择文件')
    return
  }

  // 如果用户输入了自定义 Group ID，先验证格式
  if (customGroupId.value && customGroupId.value.trim() !== '') {
    if (!validateGroupId(customGroupId.value.trim())) {
      message.warning('请修正 Group ID 格式')
      return
    }
  }

  generatingVersion.value = true
  versionResult.value = null
  editingVersion.value = false

  try {
    message.info('开始生成版本信息...')
    const response = await generateVersion(
      selectedVersionUploadId.value,
      customGroupId.value && customGroupId.value.trim() !== '' ? customGroupId.value.trim() : null
    )
    versionResult.value = response
    message.success('版本信息生成成功！')
      } catch (error) {
    console.error('生成版本信息失败:', error)
    message.error(`生成版本信息失败: ${error.message || '未知错误'}`)
  } finally {
    generatingVersion.value = false
  }
}

// 步骤4：加载已解析的文档列表（用于章节分块）
const loadSplitDocuments = async () => {
  loadingSplitList.value = true
  try {
    console.log('[loadSplitDocuments] 开始加载文档列表...')
    const response = await getDocumentUploadList(1, 100, null, null)
    splitDocuments.value = response.documents || []
    console.log('[loadSplitDocuments] 文档列表加载完成，数量:', splitDocuments.value.length)
  } catch (error) {
    console.error('加载文档列表失败:', error)
    message.error(`加载文档列表失败: ${error.message || '未知错误'}`)
  } finally {
    loadingSplitList.value = false
}
}

// 步骤4：文档选择变化处理
const handleSplitDocumentChange = () => {
  // 切换文档时清空分块结果
  splitResult.value = null
}

// 步骤4：执行章节分块
const handleSplitDocument = async () => {
  if (!selectedSplitUploadId.value) {
    message.warning('请先选择文件')
    return
  }

  if (!maxTokensPerSection.value || maxTokensPerSection.value < 1000 || maxTokensPerSection.value > 20000) {
    message.warning('每个章节的最大token数必须在1000-20000之间')
    return
  }

  splitting.value = true
  splitResult.value = null

  try {
    message.info('开始执行章节分块...')
    const response = await splitDocument(
      selectedSplitUploadId.value, 
      splitStrategy.value, 
      maxTokensPerSection.value, 
      true  // saveChunks
    )
    splitResult.value = response
    
    const strategyNames = {
      'level_1': '按一级标题',
      'level_2': '按二级标题',
      'level_3': '按三级标题',
      'level_4': '按四级标题',
      'level_5': '按五级标题',
      'fixed_token': '按固定Token',
      'no_split': '不分块'
    }
    const strategyName = strategyNames[splitStrategy.value] || splitStrategy.value
    message.success(`章节分块完成！策略: ${strategyName}, 共 ${response.statistics.total_sections} 个块`)
  } catch (error) {
    console.error('章节分块失败:', error)
    message.error(`章节分块失败: ${error.message || '未知错误'}`)
  } finally {
    splitting.value = false
  }
}

// 步骤4：根据token数获取颜色标签
const getTokenCountColor = (tokenCount, maxTokens) => {
  const ratio = tokenCount / maxTokens
  if (ratio >= 0.9) return 'red'
  if (ratio >= 0.7) return 'orange'
  if (ratio >= 0.5) return 'yellow'
  return 'green'
}

// 步骤4：章节列表表格列定义
const splitColumns = [
  {
    title: '章节ID',
    dataIndex: 'section_id',
    key: 'section_id',
    width: 120
  },
  {
    title: '标题',
    dataIndex: 'title',
    key: 'title',
    ellipsis: true
  },
  {
    title: '级别',
    dataIndex: 'level',
    key: 'level',
    width: 80,
    align: 'center'
  },
  {
    title: 'Token数',
    dataIndex: 'token_count',
    key: 'token_count',
    width: 120,
    align: 'right'
  },
  {
    title: '内容长度',
    dataIndex: 'content_length',
    key: 'content_length',
    width: 120,
    align: 'right'
  },
  {
    title: '图片数',
    dataIndex: 'image_count',
    key: 'image_count',
    width: 100,
    align: 'center'
  },
  {
    title: '表格数',
    dataIndex: 'table_count',
    key: 'table_count',
    width: 100,
    align: 'center'
  },
  {
    title: '状态',
    dataIndex: 'is_split',
    key: 'is_split',
    width: 100,
    align: 'center'
  }
]

// 步骤5：加载已解析的文档列表
const loadProcessedDocuments = async () => {
  loadingProcessList.value = true
  try {
    console.log('[loadProcessedDocuments] 开始加载文档列表...')
    const response = await getDocumentUploadList(1, 100, null, null)
    processedDocuments.value = response.documents || []
    console.log('[loadProcessedDocuments] 文档列表加载完成，数量:', processedDocuments.value.length)
    console.log('[loadProcessedDocuments] 文档状态:', processedDocuments.value.map(doc => ({ id: doc.id, status: doc.status })))
    
    // 同时更新uploadedDocuments（如果它们共享同一个数据源）
    // 这样可以确保步骤2和步骤5都能看到相同的文档列表
    if (uploadedDocuments.value.length === 0) {
      uploadedDocuments.value = processedDocuments.value
    }
  } catch (error) {
    console.error('加载文档列表失败:', error)
    message.error(`加载文档列表失败: ${error.message || '未知错误'}`)
  } finally {
    loadingProcessList.value = false
  }
}

// 步骤5：加载模板列表
const loadTemplates = async () => {
  loadingTemplates.value = true
  try {
    const response = await getTemplates(1, 100) // 加载所有模板
    templates.value = response.templates || []
    // 如果有默认模板，自动选择
    const defaultTemplate = templates.value.find(t => t.is_default)
    if (defaultTemplate && !selectedTemplateId.value) {
      selectedTemplateId.value = defaultTemplate.id
    }
  } catch (error) {
    console.error('加载模板列表失败:', error)
    message.error(`加载模板列表失败: ${error.message || '未知错误'}`)
  } finally {
    loadingTemplates.value = false
  }
}

// 步骤5：查看模板详情
const handleViewTemplate = async () => {
  if (!selectedTemplateId.value) {
    message.warning('请先选择模板')
    return
  }
  try {
    const template = await getTemplate(selectedTemplateId.value)
    Modal.info({
      title: `模板详情: ${template.name}`,
      width: 800,
      content: h('div', [
        h('p', `分类: ${template.category}`),
        h('p', `描述: ${template.description || '-'}`),
        h('p', `实体类型数: ${Object.keys(template.entity_types || {}).length}`),
        h('p', `关系类型数: ${Object.keys(template.edge_types || {}).length}`),
        h('p', `使用次数: ${template.usage_count}`)
      ])
    })
  } catch (error) {
    console.error('获取模板详情失败:', error)
    message.error(`获取模板详情失败: ${error.message || '未知错误'}`)
  }
}

// 步骤5：模板选择器过滤
const filterTemplateOption = (input, option) => {
  return option.children[0].children.toLowerCase().indexOf(input.toLowerCase()) >= 0
}

// 步骤5：处理文档并保存到Neo4j（异步任务）
const router = useRouter()
const handleProcess = async () => {
  if (!selectedProcessUploadId.value) {
    message.warning('请先选择已解析的文档')
    return
  }

  processing.value = true
  processResult.value = null

  try {
    message.info('正在提交任务...')
    const response = await submitTask({
      upload_id: selectedProcessUploadId.value,
      provider: selectedProcessProvider.value,
      max_tokens_per_section: 8000,
      use_thinking: useThinking_process.value,
      template_id: selectedTemplateId.value
    })
    
    Modal.success({
      title: '任务已提交',
      content: `任务ID: ${response.task_id}\n\n任务已提交到后台处理，请前往"任务管理"页面查看进度。`,
      okText: '前往任务管理',
      cancelText: '稍后查看',
      onOk: () => {
        router.push({ name: 'requirements-tasks' })
      }
    })
    
    // 刷新文档列表
    loadProcessedDocuments()
  } catch (error) {
    console.error('提交任务失败:', error)
    message.error(`提交失败: ${error.message || '未知错误'}`)
  } finally {
    processing.value = false
  }
}

// 步骤6：构建Community（异步任务）
const handleBuildCommunities = async () => {
  let uploadId = null
  
  if (communityBuildScope.value === 'current') {
    // 当前文档
    if (!selectedGraphUploadId.value) {
      message.warning('请先选择文档')
      return
    }
    uploadId = selectedGraphUploadId.value
  } else {
    // 跨文档
    if (!selectedCrossDocumentIds.value || selectedCrossDocumentIds.value.length < 2) {
      message.warning('跨文档构建需要至少选择2个文档')
      return
    }
    // 跨文档时，使用第一个文档的upload_id（API需要upload_id，但实际使用group_ids）
    const firstDoc = graphDocuments.value.find(doc => doc.document_id === selectedCrossDocumentIds.value[0])
    if (!firstDoc) {
      message.warning('无法找到选中的文档')
      return
    }
    uploadId = firstDoc.id
  }

  buildingCommunities.value = true
  communitiesResult.value = null
  communityTaskId.value = null

  try {
    message.info('正在提交构建Community任务...')
    const groupIds = communityBuildScope.value === 'cross' ? selectedCrossDocumentIds.value : null
    const response = await buildCommunitiesAsync(
      uploadId,
      communityBuildScope.value,
      groupIds,
      selectedCommunityProvider.value,
      useThinking_community.value
    )
    
    communityTaskId.value = response.task_id
    message.success({
      content: `任务已提交！任务ID: ${response.task_id}`,
      duration: 5
    })
    
    // 显示跳转链接
    Modal.info({
      title: '任务已提交',
      content: `任务ID: ${response.task_id}\n\n任务已提交到后台处理，请前往"任务管理"页面查看进度。`,
      okText: '前往任务管理',
      cancelText: '留在当前页面',
      onOk: () => {
        router.push('/tasks')
      }
    })
    
    // 开始轮询任务状态，任务完成后自动刷新图谱
    if (communityBuildScope.value === 'current' && selectedGraphUploadId.value) {
      pollCommunityTaskStatus(response.task_id)
    }
  } catch (error) {
    console.error('提交构建Community任务失败:', error)
    message.error(`提交失败: ${error.message || '未知错误'}`)
  } finally {
    buildingCommunities.value = false
  }
}

// 轮询构建Community任务状态
const pollCommunityTaskStatus = async (taskId) => {
  const maxAttempts = 300 // 最多轮询300次（约5分钟，每次1秒）
  let attempts = 0
  
  const poll = async () => {
    if (attempts >= maxAttempts) {
      console.log('轮询超时，停止检查任务状态')
      return
    }
    
    try {
      const task = await getTask(taskId)
      
      if (task.status === 'completed') {
        // 任务完成，自动刷新图谱
        message.success('Community构建完成！正在刷新图谱...')
        if (selectedGraphUploadId.value) {
          await handleGraphDocumentChange(selectedGraphUploadId.value)
        }
        communityTaskId.value = null
        return
      } else if (task.status === 'failed' || task.status === 'cancelled') {
        // 任务失败或取消，停止轮询
        console.log(`任务${task.status}，停止轮询`)
        communityTaskId.value = null
        return
      } else {
        // 任务仍在运行，继续轮询
        attempts++
        setTimeout(poll, 1000) // 1秒后再次检查
      }
    } catch (error) {
      console.error('轮询任务状态失败:', error)
      attempts++
      if (attempts < maxAttempts) {
        setTimeout(poll, 2000) // 出错时2秒后重试
      }
    }
  }
  
  // 延迟1秒后开始第一次轮询
  setTimeout(poll, 1000)
}

// 步骤6：加载已完成的文档列表
const loadGraphDocuments = async () => {
  loadingGraphList.value = true
  try {
    const response = await getDocumentUploadList(1, 100, null, null)
    graphDocuments.value = response.documents || []
  } catch (error) {
    console.error('加载文档列表失败:', error)
    message.error(`加载文档列表失败: ${error.message || '未知错误'}`)
  } finally {
    loadingGraphList.value = false
}
}

// 步骤6：文档选择改变时加载图谱
const handleGraphDocumentChange = async (uploadId) => {
  if (!uploadId) {
    currentGraphData.value = null
    rawGraphData.value = null
    return
  }

  const selectedDoc = graphDocuments.value.find(doc => doc.id === uploadId)
  if (!selectedDoc || !selectedDoc.document_id) {
    message.warning('该文档尚未完成处理，无法查看图谱')
    return
  }
  
  loadingGraph.value = true
  currentGraphData.value = null
  rawGraphData.value = null
  
  try {
    const response = await getDocumentGraph(selectedDoc.document_id, 'qianwen', 500)
    // 转换数据格式为GraphVisualization期望的格式
    const nodes = (response.nodes || []).map(node => ({
      id: String(node.id),
      labels: node.labels || [],
      name: node.name || node.properties?.name || '',
      type: node.type || (node.labels && node.labels[0]) || 'Entity',
      properties: node.properties || {}
    }))
    
    const edges = (response.edges || []).map(edge => ({
      id: String(edge.id),
      source: String(edge.source),
      target: String(edge.target),
      type: edge.type || 'RELATES_TO',
      properties: edge.properties || {}
    }))
    
    // 保存原始数据
    rawGraphData.value = {
      nodes: nodes,
      edges: edges
    }
    
    // 应用筛选
    applyGraphFilter()
    
    message.success(`图谱加载完成：${nodes.length} 个节点，${edges.length} 条关系`)
  } catch (error) {
    console.error('获取图谱数据失败:', error)
    message.error(`获取图谱数据失败: ${error.message || '未知错误'}`)
  } finally {
    loadingGraph.value = false
  }
}

// 步骤6：应用筛选逻辑
const applyGraphFilter = () => {
  if (!rawGraphData.value) {
    currentGraphData.value = null
    return
  }

  const config = graphFilterConfig.value
  const rawNodes = rawGraphData.value.nodes || []
  const rawEdges = rawGraphData.value.edges || []
  
  // 筛选节点
  let filteredNodes = rawNodes.filter(node => {
    const labels = node.labels || []
    const isEpisode = labels.includes('Episodic')
    const isEntity = !isEpisode && !labels.includes('Community') && labels.includes('Entity')
    const isCommunity = labels.includes('Community')
    
    if (isCommunity) {
      // Community节点筛选
      return config.showCommunities
    }
    
    if (isEpisode) {
      // Episode节点筛选
      if (!config.showEpisodes) return false
      
      // 判断Episode类型（根据name判断，后端命名规则：文档级包含"文档概览"，章节级包含"章节_"，图片包含"图片_"，表格包含"表格_"）
      const name = node.name || node.properties?.name || ''
      const isDocumentEpisode = name.includes('文档概览')
      const isSectionEpisode = name.includes('章节_')
      const isImageEpisode = name.includes('图片_')
      const isTableEpisode = name.includes('表格_')
      
      // 如果都不匹配，默认显示（可能是其他类型的Episode）
      if (!isDocumentEpisode && !isSectionEpisode && !isImageEpisode && !isTableEpisode) {
        return true
      }
      
      if (isDocumentEpisode && !config.showEpisodeTypes.document) return false
      if (isSectionEpisode && !config.showEpisodeTypes.section) return false
      if (isImageEpisode && !config.showEpisodeTypes.image) return false
      if (isTableEpisode && !config.showEpisodeTypes.table) return false
      
      return true
    } else if (isEntity) {
      // Entity节点筛选
      if (!config.showEntities) return false
      
      // 获取实体类型
      const entityType = node.type || 'Entity'
      const typeKey = config.showEntityTypes.hasOwnProperty(entityType) ? entityType : 'Entity'
      
      return config.showEntityTypes[typeKey] !== false
    }
    
    // 其他类型节点，默认显示
    return true
  })
  
  // 筛选边（只保留连接两个可见节点的边）
  const visibleNodeIds = new Set(filteredNodes.map(n => n.id))
  let filteredEdges = rawEdges.filter(edge => {
    // 关系边筛选
    if (!config.showRelations) return false
    
    // 检查关系类型
    const relationType = edge.type || 'RELATES_TO'
    const typeKey = config.showRelationTypes.hasOwnProperty(relationType) ? relationType : 'RELATES_TO'
    if (!config.showRelationTypes[typeKey]) return false
    
    // 只保留连接两个可见节点的边
    return visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target)
  })
  
  currentGraphData.value = {
    nodes: filteredNodes,
    edges: filteredEdges
  }
}

// 步骤6：监听筛选配置变化
watch(() => graphFilterConfig.value, () => {
  applyGraphFilter()
}, { deep: true })

// 步骤6：节点点击处理
const handleGraphNodeClick = (node) => {
  selectedGraphNode.value = node
  nodeDetailVisible.value = true
}

// 步骤6：边点击处理
const handleGraphEdgeClick = (edge) => {
  // 可以在这里添加边详情显示逻辑
  console.log('边点击:', edge)
}

// 步骤6：节点属性相关
const hasOtherNodeProperties = computed(() => {
  if (!selectedGraphNode.value) return false
  const props = selectedGraphNode.value.properties || {}
  const excludeKeys = ['name', 'created_at', 'updated_at', 'uuid', 'id']
  return Object.keys(props).some(key => !excludeKeys.includes(key))
})

const otherNodeProperties = computed(() => {
  if (!selectedGraphNode.value) return {}
  const props = selectedGraphNode.value.properties || {}
  const excludeKeys = ['name', 'created_at', 'updated_at', 'uuid', 'id']
  const result = {}
  Object.keys(props).forEach(key => {
    if (!excludeKeys.includes(key)) {
      result[key] = props[key]
    }
  })
  return result
})

const formatPropertyValue = (value) => {
  if (typeof value === 'object') {
    return JSON.stringify(value, null, 2)
  }
  return String(value)
}

// 查看解析结果
const handleViewParsedContent = async (record) => {
  parsedContentModalVisible.value = true
  parsedContentModalData.value = record
  parsedContentTab.value = 'parsed'
  parsedContentText.value = ''
  summaryContentText.value = ''
  structuredContentText.value = ''
  chunksContentData.value = null
  parsedContentLoading.value = true

  try {
    // 并行加载四个内容（chunks 可能不存在，单独处理错误）
    const [parsedResponse, summaryResponse, structuredResponse] = await Promise.all([
      getParsedContent(record.id),
      getSummaryContent(record.id),
      getStructuredContent(record.id)
    ])
    
    parsedContentText.value = parsedResponse.content || ''
    summaryContentText.value = summaryResponse.content || ''
    // 将 JSON 对象格式化为字符串
    structuredContentText.value = structuredResponse.content 
      ? JSON.stringify(structuredResponse.content, null, 2)
      : ''
    
    // 单独加载 chunks（可能未分块，忽略错误）
    try {
      const chunksResponse = await getChunks(record.id)
      chunksContentData.value = chunksResponse.content || null
    } catch (chunksError) {
      console.log('chunks 不可用（可能尚未分块）:', chunksError.message)
      chunksContentData.value = null
    }
  } catch (error) {
    console.error('加载解析结果失败:', error)
    message.error(`加载解析结果失败: ${error.message || '未知错误'}`)
  } finally {
    parsedContentLoading.value = false
  }
}

// 搜索选项过滤
const filterOption = (input, option) => {
  const text = option.children?.[0]?.children || option.label || ''
  return text.toLowerCase().includes(input.toLowerCase())
}

// 格式化Markdown内容，支持图片和嵌入文档
const formatMarkdown = (text, documentId = null, uploadId = null) => {
  if (!text) return ''
  
  console.log('[formatMarkdown] 输入参数:', { documentId, uploadId, textLength: text.length })
  
  // 将 /api/word-document/{document_id}/ 转换为 /api/document-upload/{upload_id}/
  if (uploadId && documentId) {
    // 转换图片URL
    text = text.replace(/\/api\/word-document\/([^/]+)\/images\/([^)]+)/g, (match, docId, imageId) => {
      console.log('[formatMarkdown] 转换图片URL:', { match, docId, documentId, imageId })
      if (docId === documentId) {
        const newUrl = `/api/document-upload/${uploadId}/images/${imageId}`
        console.log('[formatMarkdown] 图片URL转换:', match, '->', newUrl)
        return newUrl
      }
      return match
    })
    
    // 转换嵌入文档URL（包括查询参数）
    // 匹配格式: /api/word-document/{docId}/ole/{oleId}?view=preview 或 /api/word-document/{docId}/ole/{oleId}?view=download
    text = text.replace(/\/api\/word-document\/([^/]+)\/ole\/([^?\s)]+)(\?[^)\s]*)?/g, (match, docId, oleId, query) => {
      console.log('[formatMarkdown] 转换嵌入文档URL:', { match, docId, documentId, oleId, query })
      if (docId === documentId) {
        const newUrl = `/api/document-upload/${uploadId}/ole/${oleId}${query || ''}`
        console.log('[formatMarkdown] 嵌入文档URL转换:', match, '->', newUrl)
        return newUrl
      }
      return match
    })
  }
  
  // 处理图片链接
  if (uploadId) {
    text = text.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, alt, url) => {
      if (url.startsWith('/api/document-upload/')) {
        return match
      } else if (url.includes('images/')) {
        const imageId = url.split('images/')[1] || url
        const fullUrl = `/api/document-upload/${uploadId}/images/${imageId}`
        return `![${alt}](${fullUrl})`
      }
      return match
    })
    
    // ========== 优先处理嵌入文档的特殊格式（带蓝色竖条的完整结构） ==========
    // 匹配格式：
    // [嵌入文档: {文件名} ({类型})]({preview_url})
    // [查看]({preview_url}) | [下载]({download_url})
    const embeddedDocPattern = /\[嵌入文档:\s*([^\]]+?)\s*\(([^)]+)\)\]\(([^)]+)\)\s*\n\s*\[查看\]\(([^)]+)\)\s*\|\s*\[下载\]\(([^)]+)\)/g
    text = text.replace(embeddedDocPattern, (match, fileName, fileType, previewUrl1, previewUrl2, downloadUrl) => {
      // 使用第二个预览URL（更准确），如果不存在则使用第一个
      const previewUrl = previewUrl2 || previewUrl1
      
      // 提取oleId
      let oleId = previewUrl.split('/ole/')[1] || ''
      oleId = oleId.split('?')[0].split('#')[0].split('/')[0]
      if (!oleId) return match
      
      const modalId = `ole-viewer-${uploadId}-${oleId.replace(/[^a-zA-Z0-9]/g, '-')}`
      
      // 生成与"需求管理"一致的HTML结构（带蓝色竖条）
      return `<div style="margin: 15px 0; padding: 10px; background-color: #f9f9f9; border-left: 3px solid #1890ff;">
    <strong>${fileName}</strong> (${fileType})
    <br>
    <a href="javascript:void(0)" onclick="window.openOleViewer('${previewUrl}', '${downloadUrl}', '${modalId}')" style="color: #1890ff; cursor: pointer; text-decoration: underline; margin-right: 15px;">查看</a>
    <a href="javascript:void(0)" onclick="window.downloadOleFile('${downloadUrl}')" style="color: #1890ff; cursor: pointer; text-decoration: underline;">下载</a>
</div>`
    })
    
    // 处理其他嵌入文档链接（兼容旧格式）
    text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, linkText, url) => {
      if (url.includes('/ole/') && url.startsWith('/api/document-upload/')) {
        let oleId = url.split('/ole/')[1] || ''
        oleId = oleId.split('?')[0].split('#')[0].split('/')[0]
        if (!oleId) return match
        
        const baseUrl = `/api/document-upload/${uploadId}/ole/${oleId}`
        const previewUrl = `${baseUrl}?view=preview`
        const downloadUrl = `${baseUrl}?view=download`
        const modalId = `ole-viewer-${uploadId}-${oleId.replace(/[^a-zA-Z0-9]/g, '-')}`
        
        if (linkText === '查看' || linkText === '预览') {
          return `<a href="javascript:void(0)" onclick="window.openOleViewer('${previewUrl}', '${downloadUrl}', '${modalId}')" style="color: #1890ff; cursor: pointer; text-decoration: underline;">${linkText}</a>`
        } else if (linkText === '下载') {
          return `<a href="javascript:void(0)" onclick="window.downloadOleFile('${downloadUrl}')" style="color: #1890ff; cursor: pointer; text-decoration: underline;">${linkText}</a>`
        } else {
          return `<a href="javascript:void(0)" onclick="window.openOleViewer('${previewUrl}', '${downloadUrl}', '${modalId}')" style="color: #1890ff; cursor: pointer; text-decoration: underline;">${linkText}</a>`
        }
      }
      return match
    })
  }
  
  // 将Markdown格式转换为HTML
  // 先处理图片，转换为可点击链接（在转换为HTML之前）
  text = text.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, alt, url) => {
    // 如果URL是图片API路径，转换为可点击链接
    if (url.includes('/images/') || url.startsWith('/api/document-upload/')) {
      // 提取图片ID或使用alt文本
      const linkText = alt || url.split('/images/')[1] || url.split('/').pop() || '图片'
      return `[${linkText}](${url})`
    }
    return match
  })
  
  return text
    .replace(/^### (.*$)/gim, '<h3>$1</h3>')
    .replace(/^## (.*$)/gim, '<h2>$1</h2>')
    .replace(/^# (.*$)/gim, '<h1>$1</h1>')
    // 处理链接（包括转换后的图片链接）
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, linkText, url) => {
      // 如果是图片链接，显示为可点击链接
      if (url.includes('/images/') || (url.startsWith('/api/document-upload/') && url.includes('images/'))) {
        return `<a href="${url}" target="_blank" style="color: #1890ff; cursor: pointer; text-decoration: underline;">${linkText}</a>`
      }
      // 如果是OLE对象链接，已经在前面处理过了，这里直接返回
      if (url.includes('/ole/')) {
        return match
      }
      return `<a href="${url}" target="_blank">${linkText}</a>`
    })
    .replace(/\n\n/g, '<br><br>')
    .replace(/\n/g, '<br>')
}

// 加载Word文档并转换为HTML（使用后端API，包含嵌入文件链接）
const loadWordDocument = async () => {
  if (!parseResult.value?.upload_id) {
    message.warning('文档ID不存在，请先解析文档')
    return
  }
  
  loadingWordDocument.value = true
  wordDocumentHtml.value = null
  
  try {
    // 使用后端API预览Word文档（包含嵌入文件链接）
    // document_id格式为 upload_{upload_id}
    const documentId = `upload_${parseResult.value.upload_id}`
    const previewUrl = `/api/word-document/${documentId}/preview?provider=qianwen`
    console.log('加载Word文档，URL:', previewUrl)
    
    const response = await fetch(previewUrl)
    if (!response.ok) {
      const errorText = await response.text()
      console.error('API响应错误:', response.status, errorText)
      throw new Error(`加载失败: ${response.statusText}`)
    }
    
    // 获取HTML内容
    const html = await response.text()
    console.log('获取到HTML内容长度:', html.length)
    console.log('HTML内容预览:', html.substring(0, 500))
    
    // 如果返回的是完整的HTML文档，提取body内容
    const parser = new DOMParser()
    const doc = parser.parseFromString(html, 'text/html')
    const bodyContent = doc.body ? doc.body.innerHTML : html
    wordDocumentHtml.value = bodyContent || html
    console.log('设置wordDocumentHtml，长度:', wordDocumentHtml.value.length)
    console.log('wordDocumentHtml预览:', wordDocumentHtml.value.substring(0, 500))
    
    // 处理嵌入文件的链接（确保点击时使用正确的处理函数）
    setTimeout(() => {
      const viewer = document.querySelector('.word-document-viewer')
      if (viewer) {
        // 处理OLE对象的链接
        const oleLinks = viewer.querySelectorAll('a[href*="/ole/"]')
        oleLinks.forEach(link => {
          const href = link.getAttribute('href')
          if (href) {
            // 清理URL，移除重复的查询参数
            const cleanHref = href.split('?')[0]
            const isPreview = href.includes('view=preview')
            const isDownload = href.includes('view=download') || link.textContent === '下载'
            
            // 转换URL格式：从 /api/word-document/upload_{id}/ole/{ole_id} 转换为 /api/document-upload/{id}/ole/{ole_id}
            let newHref = cleanHref
            let oleId = ''
            
            if (cleanHref.includes('/api/word-document/upload_')) {
              const match = cleanHref.match(/\/api\/word-document\/upload_(\d+)\/ole\/([^?]+)/)
              if (match) {
                const uploadId = match[1]
                oleId = match[2]
                newHref = `/api/document-upload/${uploadId}/ole/${oleId}`
              } else {
                // 如果匹配失败，尝试从原始URL提取oleId
                oleId = cleanHref.match(/\/ole\/([^?]+)/)?.[1] || ''
              }
            } else {
              // 如果不是upload_格式，直接提取oleId
              oleId = cleanHref.match(/\/ole\/([^?]+)/)?.[1] || ''
            }
            
            // 移除后端添加的target和download属性（与"需求管理"保持一致）
            link.removeAttribute('target')
            link.removeAttribute('download')
            
            if (isPreview || link.textContent === '查看' || link.textContent === '预览') {
              const previewUrl = `${newHref}?view=preview`
              const downloadUrl = `${newHref}?view=download`
              const modalId = `ole-viewer-${parseResult.value.upload_id}-${oleId.replace(/[^a-zA-Z0-9]/g, '-')}`
              
              // 设置onclick处理器（与"需求管理"保持一致）
              link.onclick = (e) => {
                e.preventDefault()
                if (window.openOleViewer) {
                  window.openOleViewer(previewUrl, downloadUrl, modalId)
                } else {
                  window.open(previewUrl, '_blank')
                }
                return false
              }
            } else if (isDownload || link.textContent === '下载') {
              const downloadUrl = `${newHref}?view=download`
              // 设置onclick处理器（与"需求管理"保持一致）
              link.onclick = (e) => {
                e.preventDefault()
                if (window.downloadOleFile) {
                  window.downloadOleFile(downloadUrl)
                } else {
                  // 创建一个临时a元素来触发下载
                  const a = document.createElement('a')
                  a.href = downloadUrl
                  a.download = ''
                  document.body.appendChild(a)
                  a.click()
                  document.body.removeChild(a)
                }
                return false
              }
            }
          }
        })
      }
    }, 100)
    
    message.success('Word文档加载成功')
  } catch (error) {
    console.error('加载Word文档失败:', error)
    message.error(`加载Word文档失败: ${error.message || '未知错误'}`)
  } finally {
    loadingWordDocument.value = false
  }
}

// 打开嵌入文档查看器
const openOleViewer = (previewUrl, downloadUrl, modalId) => {
  // 检查是否已存在模态框，如果存在则先移除
  const existingModal = document.getElementById(modalId)
  if (existingModal) {
    document.body.removeChild(existingModal)
  }
  
  // 创建模态框
  const modal = document.createElement('div')
  modal.id = modalId
  modal.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.7);
    z-index: 10000;
    display: flex;
    align-items: center;
    justify-content: center;
  `
  
  const content = document.createElement('div')
  content.style.cssText = `
    background: white;
    border-radius: 8px;
    width: 90%;
    height: 90%;
    max-width: 1200px;
    display: flex;
    flex-direction: column;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
  `
  
  const header = document.createElement('div')
  header.style.cssText = `
    padding: 16px;
    border-bottom: 1px solid #e8e8e8;
    display: flex;
    justify-content: space-between;
    align-items: center;
  `
  
  const title = document.createElement('span')
  title.textContent = '嵌入文档查看器'
  title.style.cssText = 'font-size: 16px; font-weight: bold;'
  
  const buttonGroup = document.createElement('div')
  buttonGroup.style.cssText = 'display: flex; gap: 8px;'
  
  const downloadBtn = document.createElement('button')
  downloadBtn.textContent = '下载'
  downloadBtn.style.cssText = `
    background: #1890ff;
    color: white;
    border: none;
    padding: 6px 16px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 14px;
  `
  downloadBtn.onclick = () => {
    window.open(downloadUrl, '_blank')
  }
  
  const closeBtn = document.createElement('button')
  closeBtn.textContent = '×'
  closeBtn.style.cssText = `
    background: none;
    border: none;
    font-size: 24px;
    cursor: pointer;
    color: #666;
    padding: 0;
    width: 30px;
    height: 30px;
    line-height: 30px;
  `
  closeBtn.onclick = () => {
    document.body.removeChild(modal)
  }
  
  buttonGroup.appendChild(downloadBtn)
  buttonGroup.appendChild(closeBtn)
  header.appendChild(title)
  header.appendChild(buttonGroup)
  
  const body = document.createElement('div')
  body.style.cssText = `
    flex: 1;
    overflow: auto;
    padding: 0;
  `
  
  // 使用iframe显示预览内容（后端会返回HTML格式的Excel预览）
  const iframe = document.createElement('iframe')
  iframe.style.cssText = 'width: 100%; height: 100%; border: none;'
  iframe.setAttribute('sandbox', 'allow-same-origin allow-scripts allow-popups allow-forms')
  
  // 添加加载状态
  const loadingDiv = document.createElement('div')
  loadingDiv.style.cssText = 'text-align: center; padding: 40px; color: #666;'
  loadingDiv.innerHTML = '<p>正在加载预览...</p>'
  body.appendChild(loadingDiv)
  
  // 先添加iframe到DOM，然后设置src
  body.appendChild(iframe)
  
  // 监听iframe加载完成
  iframe.onload = () => {
    // 移除加载提示
    if (body.contains(loadingDiv)) {
      body.removeChild(loadingDiv)
    }
  }
  
  // 如果加载失败，显示错误信息
  iframe.onerror = () => {
    if (body.contains(loadingDiv)) {
      body.removeChild(loadingDiv)
    }
    body.innerHTML = `
      <div style="text-align: center; padding: 40px;">
        <p style="color: #ff4d4f; margin-bottom: 16px;">预览加载失败</p>
        <p style="color: #666; margin-bottom: 16px;">请尝试下载文件后查看。</p>
        <a href="javascript:void(0)" onclick="window.downloadOleFile('${downloadUrl}')" style="color: #1890ff; text-decoration: underline; display: inline-block; padding: 8px 16px; background: #f0f0f0; border-radius: 4px; cursor: pointer;">下载文件</a>
      </div>
    `
  }
  
  // 设置超时处理（10秒）
  const timeoutId = setTimeout(() => {
    if (body.contains(loadingDiv)) {
      // 如果10秒后还在加载，显示错误信息
      body.removeChild(loadingDiv)
      body.innerHTML = `
        <div style="text-align: center; padding: 40px;">
          <p style="color: #ff4d4f; margin-bottom: 16px;">预览加载超时</p>
          <p style="color: #666; margin-bottom: 16px;">请尝试下载文件后查看。</p>
          <a href="javascript:void(0)" onclick="window.downloadOleFile('${downloadUrl}')" style="color: #1890ff; text-decoration: underline; display: inline-block; padding: 8px 16px; background: #f0f0f0; border-radius: 4px; cursor: pointer;">下载文件</a>
        </div>
      `
    }
  }, 10000)
  
  // 设置iframe的src（延迟设置，确保DOM已准备好）
  setTimeout(() => {
    iframe.src = previewUrl
    // 如果iframe加载成功，清除超时
    iframe.onload = () => {
      clearTimeout(timeoutId)
      if (body.contains(loadingDiv)) {
        body.removeChild(loadingDiv)
      }
    }
  }, 100)
  
  content.appendChild(header)
  content.appendChild(body)
  modal.appendChild(content)
  
  // 点击背景关闭
  modal.onclick = (e) => {
    if (e.target === modal) {
      document.body.removeChild(modal)
    }
  }
  
  document.body.appendChild(modal)
}

// 直接下载OLE文件（不使用弹窗）
const downloadOleFile = (downloadUrl) => {
  // 创建一个临时的a标签来触发下载
  const link = document.createElement('a')
  link.href = downloadUrl
  link.target = '_blank'
  link.download = '' // 让浏览器自动处理文件名
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

// 将函数挂载到window对象，以便在HTML中调用
if (typeof window !== 'undefined') {
  window.openOleViewer = openOleViewer
  window.downloadOleFile = downloadOleFile
}

// 初始化加载
onMounted(() => {
  console.log('[onMounted] 组件已挂载，activeTab:', activeTab.value)
  loadDocumentList()
  // 始终加载文件列表，不管当前是哪个Tab
  console.log('[onMounted] 开始加载文件列表...')
  loadUploadedDocuments()
  loadProcessedDocuments()
  loadGraphDocuments()
  loadTemplates() // 加载模板列表
})

// 监听Tab切换，自动加载对应的文件列表
watch(activeTab, (newTab, oldTab) => {
  console.log('[watch] Tab切换:', oldTab, '->', newTab)
  if (newTab === 'parse') {
    console.log('[watch] 切换到步骤2，重新加载文件列表...')
    loadUploadedDocuments()
  } else if (newTab === 'version') {
    console.log('[watch] 切换到步骤3，重新加载文档列表...')
    loadVersionDocuments()
    loadGroupIds() // 加载 Group ID 列表
  } else if (newTab === 'split') {
    console.log('[watch] 切换到步骤4，重新加载文档列表...')
    loadSplitDocuments()
  } else if (newTab === 'process') {
    console.log('[watch] 切换到步骤5，重新加载文档列表...')
    loadProcessedDocuments()
  } else if (newTab === 'graph') {
    console.log('[watch] 切换到步骤6，重新加载文档列表...')
    loadGraphDocuments()
  }
})
</script>

<style scoped>
.step-content {
  padding: 16px 0;
}

.step-content :deep(.ant-upload) {
  width: 100%;
}

.step-content :deep(.ant-upload-select) {
  width: 100%;
  display: block;
}

.step-content code {
  font-family: 'Courier New', monospace;
  font-size: 12px;
}

.word-document-viewer {
  font-family: 'Microsoft YaHei', 'SimSun', 'Times New Roman', serif;
  line-height: 1.6;
  color: #333;
}

.word-document-viewer :deep(p) {
  margin: 8px 0;
}

.word-document-viewer :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 16px 0;
  border: 1px solid #ddd;
}

.word-document-viewer :deep(table td),
.word-document-viewer :deep(table th) {
  border: 1px solid #ddd;
  padding: 8px;
  text-align: left;
}

.word-document-viewer :deep(table th) {
  background-color: #f5f5f5;
  font-weight: bold;
}

.word-document-viewer :deep(h1) {
  font-size: 24px;
  font-weight: bold;
  margin: 16px 0;
}

.word-document-viewer :deep(h2) {
  font-size: 20px;
  font-weight: bold;
  margin: 14px 0;
}

.word-document-viewer :deep(h3) {
  font-size: 16px;
  font-weight: bold;
  margin: 12px 0;
}

.word-document-viewer :deep(strong) {
  font-weight: bold;
}

.word-document-viewer :deep(em) {
  font-style: italic;
}

.word-document-viewer :deep(ul),
.word-document-viewer :deep(ol) {
  margin: 8px 0;
  padding-left: 24px;
}
</style>

