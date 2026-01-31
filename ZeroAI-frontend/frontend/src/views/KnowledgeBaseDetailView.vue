<template>
  <a-layout class="kb-layout" style="min-height: calc(100vh - 64px)">
    <!-- 第一列：左侧导航 -->
    <a-layout-sider :width="leftSiderWidth" class="left-sider kb-sider-left">
      <div style="padding: 16px">
        <div class="kb-category-section">
          <div class="category-header">
            <FolderOutlined style="font-size: 20px" />
            <span style="font-weight: bold">个人知识库</span>
            <a-button type="text" size="small" @click="handleCreateKB('private')" class="add-kb-btn">
              <PlusOutlined />
            </a-button>
          </div>
          <div class="kb-list">
            <div
              v-for="kb in privateKBs"
              :key="kb.id"
              class="kb-item"
              :class="{ active: selectedKbId === kb.id }"
              @click="selectKnowledgeBase(kb.id)"
            >
              <component :is="getIconComponent(kb.cover_icon)" v-if="kb.cover_icon" class="kb-item-icon" />
              <FolderOutlined v-else class="kb-item-icon" />
              <span>{{ kb.name }}</span>
            </div>
          </div>
        </div>

        <div class="kb-category-section" style="margin-top: 24px">
          <div class="category-header">
            <TeamOutlined style="font-size: 20px" />
            <span style="font-weight: bold">共享知识库</span>
          </div>
          <a-collapse v-model:activeKey="sharedCollapseKeys" :bordered="false" ghost>
            <a-collapse-panel key="my_created_shared">
              <template #header>
                <div style="display: flex; align-items: center; width: 100%; justify-content: space-between;">
                  <span>我创建的</span>
                  <a-button type="text" size="small" @click.stop="handleCreateKB('shared')" class="add-kb-btn-inline">
                    <PlusOutlined />
                  </a-button>
                </div>
              </template>
              <div class="kb-list">
                <div
                  v-for="kb in myCreatedSharedKBs"
                  :key="kb.id"
                  class="kb-item"
                  :class="{ active: selectedKbId === kb.id }"
                  @click="selectKnowledgeBase(kb.id)"
                >
                  <component :is="getIconComponent(kb.cover_icon)" v-if="kb.cover_icon" class="kb-item-icon" />
                  <FolderOutlined v-else class="kb-item-icon" />
                  <span>{{ kb.name }}</span>
                </div>
              </div>
            </a-collapse-panel>
            <a-collapse-panel key="my_joined_shared" header="我加入的">
              <div class="kb-list">
                <div
                  v-for="kb in myJoinedSharedKBs"
                  :key="kb.id"
                  class="kb-item"
                  :class="{ active: selectedKbId === kb.id }"
                  @click="selectKnowledgeBase(kb.id)"
                >
                  <component :is="getIconComponent(kb.cover_icon)" v-if="kb.cover_icon" class="kb-item-icon" />
                  <FolderOutlined v-else class="kb-item-icon" />
                  <span>{{ kb.name }}</span>
                </div>
              </div>
            </a-collapse-panel>
          </a-collapse>
        </div>
      </div>
      <!-- 拖拽条 -->
      <div
        class="resize-handle resize-handle-right"
        @mousedown="(e) => { initResize(e); startResize('left'); }"
      ></div>
    </a-layout-sider>

    <!-- 第二列：中间内容区 -->
    <a-layout-content class="kb-content-middle">
      <div v-if="selectedKB" class="kb-detail-container">
        <!-- 知识库头部 -->
        <div class="kb-header">
          <div class="kb-title-section">
            <component :is="getIconComponent(selectedKB.cover_icon)" v-if="selectedKB.cover_icon" style="font-size: 32px; margin-right: 12px" />
            <FolderOutlined v-else style="font-size: 32px; margin-right: 12px" />
            <div>
              <h1 style="margin: 0; font-size: 24px">{{ selectedKB.name }}</h1>
              <div style="margin-top: 8px; color: #8c8c8c">
                <span>{{ selectedKB.member_count }}加入</span>
              </div>
            </div>
          </div>
          <div class="kb-actions">
            <a-button 
              type="text" 
              @click="handleShareToAll" 
              v-if="isAdminUser && selectedKB.visibility === 'shared'"
              title="一键共享：向所有用户发送加入邀请"
            >
              <ShareAltOutlined />
            </a-button>
            <a-button type="text" @click="handleEdit" v-if="isOwner">
              <EditOutlined />
            </a-button>
            <a-button type="text" @click="handleDelete" v-if="isOwner" danger>
              <DeleteOutlined />
            </a-button>
            <a-button 
              type="text" 
              @click="handleLeave" 
              v-if="!isOwner && isMember"
              title="退出知识库"
            >
              <LogoutOutlined />
            </a-button>
          </div>
        </div>

        <!-- 描述 -->
        <a-tooltip v-if="isOwner && description" :title="description" placement="top">
          <a-input
            v-model:value="description"
            placeholder="快来填写简介吧~"
            style="margin-top: 16px; margin-bottom: 16px"
            @blur="handleUpdateDescription"
            :disabled="true"
          />
        </a-tooltip>
        <a-input
          v-else-if="isOwner && !description"
          v-model:value="description"
          placeholder="快来填写简介吧~"
          style="margin-top: 16px; margin-bottom: 16px"
          @blur="handleUpdateDescription"
          :disabled="true"
        />
        <a-tooltip v-else-if="selectedKB?.description" :title="selectedKB.description" placement="top">
          <div style="margin-top: 16px; margin-bottom: 16px; color: #8c8c8c">
            {{ selectedKB.description || '暂无描述' }}
          </div>
        </a-tooltip>
        <div v-else style="margin-top: 16px; margin-bottom: 16px; color: #8c8c8c">
          {{ selectedKB?.description || '暂无描述' }}
        </div>

        <!-- 内容区域 -->
        <a-card :title="`内容(${documents.length})`" style="margin-top: 24px">
          <template #extra>
            <div class="content-controls">
              <a-input-search
                v-model:value="searchKeyword"
                placeholder="搜索文档"
                style="width: 200px"
                @search="loadDocuments"
              />
              <a-space>
                <a-button type="text" @click="loadDocuments">
                  <UnorderedListOutlined />
                </a-button>
                <a-button 
                  type="text" 
                  @click="showDocumentLibraryModal = true" 
                  v-if="isOwner || isEditor"
                  title="从文档库选择文档"
                >
                  <PlusOutlined />
                </a-button>
              </a-space>
            </div>
          </template>

          <div v-if="documentsLoading" style="text-align: center; padding: 40px">
            <a-spin />
          </div>
          <div v-else-if="documents.length === 0" style="text-align: center; padding: 40px">
            <a-empty description="暂无文档" />
          </div>
          <div v-else class="document-list">
            <div
              v-for="item in documents"
              :key="item.id"
              class="document-item"
              @click="handleViewDocument(item)"
              style="cursor: pointer"
            >
              <FileTextOutlined style="font-size: 20px; color: #1890ff; margin-right: 12px" />
              <div class="document-info" style="flex: 1">
                <div class="document-name">{{ item.file_name }}</div>
                <div class="document-meta">
                  <span v-if="item.file_extension === 'docx' || item.file_extension === 'doc'">
                    W WORD
                  </span>
                  <span v-else-if="item.file_extension === 'pdf'">
                    PDF
                  </span>
                  <span v-else>{{ item.file_extension?.toUpperCase() }}</span>
                  <span style="margin-left: 8px">{{ formatDateTime(item.upload_time) }}</span>
                </div>
              </div>
              <div style="margin-left: auto; display: flex; align-items: center; gap: 8px" @click.stop>
                <a-tag v-if="item.status === 'error'" color="red">
                  解析失败
                </a-tag>
                <a-button
                  v-if="isEditor || isOwner"
                  type="text"
                  danger
                  size="small"
                  @click="handleDeleteDocument(item)"
                  :loading="deletingDocumentId === item.id"
                >
                  <DeleteOutlined />
                  删除
                </a-button>
              </div>
            </div>
          </div>
          
          <div v-if="documents.length > 0" style="text-align: center; margin-top: 16px; color: #8c8c8c; font-size: 12px">
            没有更多内容了
          </div>
        </a-card>

      </div>

      <a-empty v-else description="请选择一个知识库" />
      
      <!-- 编辑知识库弹窗 -->
      <a-modal
        v-model:open="editModalVisible"
        title="编辑知识库"
        @ok="handleEditConfirm"
        @cancel="handleEditCancel"
      >
        <a-form
          ref="editFormRef"
          :model="editForm"
          :label-col="{ span: 6 }"
          :wrapper-col="{ span: 18 }"
        >
          <a-form-item label="知识库名称" name="name" :rules="[{ required: true, message: '请输入知识库名称' }]">
            <a-input v-model:value="editForm.name" placeholder="请输入知识库名称" />
          </a-form-item>
          <a-form-item label="描述" name="description">
            <a-textarea
              v-model:value="editForm.description"
              placeholder="请输入知识库描述"
              :rows="3"
            />
          </a-form-item>
          <a-form-item label="可见性" name="visibility">
            <a-radio-group v-model:value="editForm.visibility">
              <a-radio value="private">个人</a-radio>
              <a-radio value="shared">共享</a-radio>
            </a-radio-group>
            <div style="margin-top: 8px; color: #8c8c8c; font-size: 12px">
              <div v-if="editForm.visibility === 'private' && selectedKB && selectedKB.visibility === 'shared'">
                注意：将共享知识库改为个人知识库后，已加入的成员将无法再访问，需要重新加入。
              </div>
              <div v-else-if="editForm.visibility === 'shared' && selectedKB && selectedKB.visibility === 'private'">
                注意：将个人知识库改为共享知识库后，之前被移除的成员需要重新加入才能使用。
              </div>
            </div>
          </a-form-item>
        </a-form>
      </a-modal>
      
      <!-- 从文档库选择文档弹窗 -->
      <a-modal
        v-model:open="showDocumentLibraryModal"
        title="从文档库选择文档"
        :width="900"
        :confirm-loading="addingDocuments"
        @ok="handleAddDocumentsFromLibrary"
        @cancel="handleCancelDocumentLibrary"
        :ok-text="selectedLibraryDocuments.length > 0 ? `添加 ${selectedLibraryDocuments.length} 个文档` : '添加'"
        :ok-button-props="{ disabled: selectedLibraryDocuments.length === 0 }"
      >
        <div style="margin-bottom: 16px">
          <a-input-search
            v-model:value="librarySearchKeyword"
            placeholder="搜索文档..."
            style="width: 300px"
            @search="loadLibraryDocuments"
            allow-clear
          />
          <a-button style="margin-left: 8px" @click="loadLibraryDocuments">
            <template #icon><ReloadOutlined /></template>
            刷新
          </a-button>
        </div>
        
        <a-table
          :columns="libraryDocumentColumns"
          :data-source="libraryDocuments"
          :row-selection="{
            type: 'checkbox',
            selectedRowKeys: selectedLibraryDocuments,
            onChange: (selectedRowKeys) => {
              selectedLibraryDocuments = selectedRowKeys
            }
          }"
          :loading="libraryDocumentsLoading"
          :pagination="{
            current: libraryDocumentsPage,
            pageSize: libraryDocumentsPageSize,
            total: libraryDocumentsTotal,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 个文档`,
            onChange: (page, pageSize) => {
              libraryDocumentsPage = page
              libraryDocumentsPageSize = pageSize
              loadLibraryDocuments()
            }
          }"
          row-key="id"
          size="small"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'status'">
              <a-tag :color="getLibraryDocumentStatusColor(record.status)">
                {{ getLibraryDocumentStatusText(record.status) }}
              </a-tag>
            </template>
            <template v-else-if="column.key === 'file_size'">
              {{ formatFileSize(record.file_size) }}
            </template>
            <template v-else-if="column.key === 'created_at'">
              {{ formatDateTime(record.created_at) }}
            </template>
          </template>
        </a-table>
        
        <!-- 配置面板（默认展开） -->
        <a-divider />
        <div style="margin-top: 16px">
          <h4 style="margin-bottom: 16px">处理配置</h4>
          
          <a-form-item label="分块策略" style="margin-bottom: 16px">
            <a-select v-model:value="uploadConfig.chunk_strategy">
              <a-select-option value="level_1">按一级标题（推荐）</a-select-option>
              <a-select-option value="level_2">按二级标题</a-select-option>
              <a-select-option value="level_3">按三级标题</a-select-option>
              <a-select-option value="level_4">按四级标题</a-select-option>
              <a-select-option value="level_5">按五级标题</a-select-option>
              <a-select-option value="fixed_token">按固定Token</a-select-option>
              <a-select-option value="no_split">不分块</a-select-option>
            </a-select>
          </a-form-item>
          
          <a-form-item label="最大Token数" style="margin-bottom: 16px">
            <a-input-number
              v-model:value="uploadConfig.max_tokens_per_section"
              :min="1000"
              :max="20000"
              :step="1000"
              style="width: 100%"
            />
          </a-form-item>
          
          <a-form-item label="模板生成方案" style="margin-bottom: 16px">
            <a-radio-group v-model:value="uploadConfig.analysis_mode">
              <a-radio value="smart_segment">智能分段</a-radio>
              <a-radio value="full_chunk">全文分块</a-radio>
            </a-radio-group>
          </a-form-item>
        </div>
      </a-modal>
      
      <!-- 创建知识库弹窗 -->
      <a-modal
        v-model:visible="createModalVisible"
        title="创建知识库"
        @ok="handleCreateConfirm"
        @cancel="createModalVisible = false"
      >
        <a-form
          ref="createFormRef"
          :model="createForm"
          :label-col="{ span: 6 }"
          :wrapper-col="{ span: 18 }"
        >
          <a-form-item
            label="知识库名称"
            name="name"
            :rules="[{ required: true, message: '请输入知识库名称' }]"
          >
            <a-input v-model:value="createForm.name" placeholder="请输入知识库名称" />
          </a-form-item>
          <a-form-item
            label="描述"
            name="description"
          >
            <a-textarea
              v-model:value="createForm.description"
              placeholder="请输入知识库描述（可选）"
              :rows="3"
            />
          </a-form-item>
          <a-form-item
            label="可见性"
            name="visibility"
          >
            <a-radio-group v-model:value="createForm.visibility">
              <a-radio value="private">个人</a-radio>
              <a-radio value="shared">共享</a-radio>
            </a-radio-group>
          </a-form-item>
        </a-form>
      </a-modal>
      
      <!-- 拖拽条 -->
      <div
        class="resize-handle resize-handle-right"
        @mousedown="(e) => { initResize(e); startResize('right'); }"
      ></div>
    </a-layout-content>

    <!-- 第三列：右侧问答面板 -->
    <a-layout-sider :width="rightSiderWidth" class="right-sider kb-sider-right" :collapsed="false">
      <div class="qa-panel">
        <!-- 中间内容区 -->
        <div 
          class="qa-panel-content"
          style="
            border: 1px solid #d9d9d9;
            border-radius: 8px;
            padding: 16px;
            min-height: 400px;
            max-height: 600px;
            overflow-y: auto;
            background: #fafafa;
            margin: 16px;
          "
          ref="chatMessagesRef"
        >
          <!-- 空状态 -->
          <a-empty
            v-if="chatMessages.length === 0"
            description="请先选择知识库，然后开始提问。系统会自动从该知识库的文档中检索相关信息来回答您的问题。"
            style="margin: 60px 0"
          />

          <!-- 消息列表 -->
          <div v-for="(msg, index) in chatMessages" :key="index" style="margin-bottom: 24px">
            <!-- 用户消息 -->
            <div v-if="msg.role === 'user'" style="display: flex; justify-content: flex-end; margin-bottom: 8px">
              <div
                style="
                  max-width: 70%;
                  background: #1890ff;
                  color: white;
                  padding: 12px 16px;
                  border-radius: 12px 12px 4px 12px;
                  word-wrap: break-word;
                "
              >
                <div style="white-space: pre-wrap">{{ msg.content }}</div>
                <div style="font-size: 11px; opacity: 0.8; margin-top: 4px">
                  {{ formatTime(msg.timestamp) }}
                </div>
              </div>
            </div>

            <!-- AI消息 -->
            <div v-else style="display: flex; justify-content: flex-start; margin-bottom: 8px">
              <div style="max-width: 70%">
                <!-- AI回答内容 -->
                <div
                  style="
                    background: white;
                    border: 1px solid #e8e8e8;
                    padding: 12px 16px;
                    border-radius: 12px 12px 12px 4px;
                    word-wrap: break-word;
                    margin-bottom: 8px;
                  "
                >
                  <div 
                    v-html="formatMarkdown(msg.content)"
                    style="font-family: 'Microsoft YaHei', sans-serif; font-size: 14px; line-height: 1.8;"
                  ></div>
                  <div style="font-size: 11px; color: #999; margin-top: 8px; display: flex; align-items: center; gap: 8px">
                    <span>{{ formatTime(msg.timestamp) }}</span>
                    <a-tag v-if="msg.has_context" color="green" size="small">基于知识图谱</a-tag>
                    <a-tag v-else color="orange" size="small">通用回答</a-tag>
                    <a-button
                      type="link"
                      size="small"
                      style="padding: 0; height: auto"
                      @click="copyMessage(msg.content)"
                    >
                      复制
                    </a-button>
                  </div>
                </div>

                <!-- 检索结果面板 -->
                <a-collapse
                  v-if="(msg.retrieval_results && Array.isArray(msg.retrieval_results) && msg.retrieval_results.length > 0) || (msg.retrieval_count && msg.retrieval_count > 0)"
                  :bordered="false"
                  style="background: white; border: 1px solid #e8e8e8; border-radius: 8px"
                >
                  <template #expandIcon="{ isActive }">
                    <CaretRightOutlined :rotate="isActive ? 90 : 0" />
                  </template>
                  <a-collapse-panel
                    :key="index"
                    :header="`检索结果 (${msg.retrieval_count || 0} 个，耗时 ${msg.retrieval_time?.toFixed(0) || 0}ms)`"
                  >
                    <div style="max-height: 300px; overflow-y: auto">
                      <!-- Community列表（优先展示） -->
                      <div v-if="getCommunities(msg.retrieval_results).length > 0" style="margin-bottom: 16px">
                        <a-typography-title :level="5" style="margin-bottom: 8px">Community（高层次概念）</a-typography-title>
                        <a-list
                          :data-source="getCommunities(msg.retrieval_results)"
                          size="small"
                          :pagination="false"
                        >
                          <template #renderItem="{ item }">
                            <a-list-item 
                              style="padding: 8px 0; cursor: pointer;"
                              @click="handleViewRetrievalDetail(item)"
                            >
                              <a-list-item-meta>
                                <template #title>
                                  <a-space>
                                    <a-tag color="purple" size="small">Community</a-tag>
                                    <strong>{{ item.properties?.name || '未知' }}</strong>
                                    <a-tag v-if="item.properties?.member_count !== undefined" color="blue" size="small">
                                      {{ item.properties.member_count }}个成员
                                    </a-tag>
                                    <a-tag v-if="item.score" color="orange" size="small">
                                      相似度: {{ item.score.toFixed(1) }}%
                                    </a-tag>
                                    <a-button 
                                      type="text" 
                                      size="small" 
                                      @click.stop="handleViewRetrievalDetail(item)"
                                      style="padding: 0; height: auto;"
                                    >
                                      <template #icon><EyeOutlined /></template>
                                      查看详情
                                    </a-button>
                                  </a-space>
                                </template>
                                <template #description>
                                  <div style="font-size: 12px; color: #999">
                                    <div v-if="item.properties?.summary" style="margin-bottom: 4px">
                                      {{ item.properties.summary }}
                                    </div>
                                  </div>
                                </template>
                              </a-list-item-meta>
                            </a-list-item>
                          </template>
                        </a-list>
                      </div>

                      <!-- Episode列表 -->
                      <div v-if="getEpisodes(msg.retrieval_results).length > 0" style="margin-bottom: 16px">
                        <a-typography-title :level="5" style="margin-bottom: 8px">Episode（完整上下文）</a-typography-title>
                        <a-list
                          :data-source="getEpisodes(msg.retrieval_results)"
                          size="small"
                          :pagination="false"
                        >
                          <template #renderItem="{ item }">
                            <a-list-item 
                              style="padding: 8px 0; cursor: pointer;"
                              @click="handleViewRetrievalDetail(item)"
                            >
                              <a-list-item-meta>
                                <template #title>
                                  <a-space>
                                    <a-tag color="purple" size="small">Episode</a-tag>
                                    <strong>{{ item.properties?.name || '未知' }}</strong>
                                    <a-tag v-if="item.score" color="orange" size="small">
                                      相似度: {{ item.score.toFixed(1) }}%
                                    </a-tag>
                                    <a-button 
                                      type="text" 
                                      size="small" 
                                      @click.stop="handleViewRetrievalDetail(item)"
                                      style="padding: 0; height: auto;"
                                    >
                                      <template #icon><EyeOutlined /></template>
                                      查看详情
                                    </a-button>
                                  </a-space>
                                </template>
                                <template #description>
                                  <div style="font-size: 12px; color: #999">
                                    <div v-if="item.properties?.content" style="margin-top: 4px; color: #666; max-height: 100px; overflow: hidden; text-overflow: ellipsis">
                                      {{ item.properties.content.length > 200 ? item.properties.content.substring(0, 200) + '...' : item.properties.content }}
                                    </div>
                                  </div>
                                </template>
                              </a-list-item-meta>
                            </a-list-item>
                          </template>
                        </a-list>
                      </div>

                      <!-- 关系列表 -->
                      <div v-if="getRelationships(msg.retrieval_results).length > 0" style="margin-bottom: 16px">
                        <a-typography-title :level="5" style="margin-bottom: 8px">关系</a-typography-title>
                        <a-list
                          :data-source="getRelationships(msg.retrieval_results)"
                          size="small"
                          :pagination="false"
                        >
                          <template #renderItem="{ item }">
                            <a-list-item 
                              style="padding: 8px 0; cursor: pointer;"
                              @click="handleViewRetrievalDetail(item)"
                            >
                              <a-list-item-meta>
                                <template #title>
                                  <a-space>
                                    <a-tag color="blue" size="small">{{ item.rel_type || item.type }}</a-tag>
                                    <span>
                                      <strong>{{ item.source_name || `节点${item.source}` }}</strong>
                                      <ArrowRightOutlined style="margin: 0 8px" />
                                      <strong>{{ item.target_name || `节点${item.target}` }}</strong>
                                    </span>
                                    <a-tag v-if="item.score" color="orange" size="small">
                                      相似度: {{ item.score.toFixed(1) }}%
                                    </a-tag>
                                    <a-button 
                                      type="text" 
                                      size="small" 
                                      @click.stop="handleViewRetrievalDetail(item)"
                                      style="padding: 0; height: auto;"
                                    >
                                      <template #icon><EyeOutlined /></template>
                                      查看详情
                                    </a-button>
                                  </a-space>
                                </template>
                                <template #description>
                                  <div style="font-size: 12px; color: #999">
                                    <div v-if="item.fact" style="margin-top: 4px; color: #666">
                                      {{ item.fact }}
                                    </div>
                                  </div>
                                </template>
                              </a-list-item-meta>
                            </a-list-item>
                          </template>
                        </a-list>
                      </div>

                      <!-- 实体列表 -->
                      <div v-if="getEntities(msg.retrieval_results).length > 0">
                        <a-typography-title :level="5" style="margin-bottom: 8px">实体</a-typography-title>
                        <a-list
                          :data-source="getEntities(msg.retrieval_results)"
                          size="small"
                          :pagination="false"
                        >
                          <template #renderItem="{ item }">
                            <a-list-item 
                              style="padding: 8px 0; cursor: pointer;"
                              @click="handleViewRetrievalDetail(item)"
                            >
                              <a-list-item-meta>
                                <template #title>
                                  <a-space>
                                    <a-tag :color="getTypeColor(item.labels?.[0])" size="small">
                                      {{ item.labels?.[0] || 'Entity' }}
                                    </a-tag>
                                    <strong>{{ item.properties?.name || '未知' }}</strong>
                                    <a-tag v-if="item.score" color="orange" size="small">
                                      相似度: {{ item.score.toFixed(1) }}%
                                    </a-tag>
                                    <a-button 
                                      type="text" 
                                      size="small" 
                                      @click.stop="handleViewRetrievalDetail(item)"
                                      style="padding: 0; height: auto;"
                                    >
                                      <template #icon><EyeOutlined /></template>
                                      查看详情
                                    </a-button>
                                  </a-space>
                                </template>
                              </a-list-item-meta>
                            </a-list-item>
                          </template>
                        </a-list>
                      </div>
                    </div>
                  </a-collapse-panel>
                </a-collapse>

                <!-- 无检索结果提示 -->
                <a-alert
                  v-else-if="!msg.has_context"
                  message="未检索到知识图谱信息"
                  description="本次回答基于LLM的通用知识，未使用知识图谱数据。"
                  type="warning"
                  show-icon
                  style="margin-top: 8px"
                  size="small"
                />
              </div>
            </div>
          </div>

          <!-- 加载状态 -->
          <div v-if="chatLoading" style="text-align: center; padding: 20px">
            <a-spin size="large">
              <template #indicator>
                <LoadingOutlined style="font-size: 24px" spin />
              </template>
            </a-spin>
            <div style="margin-top: 12px; color: #999">
              正在检索知识图谱...
            </div>
          </div>
        </div>

        <!-- Agent模式配置面板（已隐藏，改为通过设置图标打开模态框） -->
        <div v-if="false" class="agent-config-panel" style="padding: 16px; border-top: 1px solid #f0f0f0; background: #fafafa">
          <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }" size="small">
            <a-row :gutter="16">
              <a-col :span="8">
                <a-form-item label="最大迭代次数">
                  <a-input-number
                    v-model:value="agentConfig.maxIterations"
                    :min="1"
                    :max="10"
                    style="width: 100%"
                  />
                </a-form-item>
              </a-col>
              <a-col :span="8">
                <a-form-item label="质量阈值">
                  <a-slider
                    v-model:value="agentConfig.qualityThreshold"
                    :min="0"
                    :max="100"
                    style="width: 100%"
                  />
                  <span style="font-size: 12px; color: #8c8c8c">{{ agentConfig.qualityThreshold }}</span>
                </a-form-item>
              </a-col>
              <a-col :span="8">
                <a-form-item label="检索数量">
                  <a-input-number
                    v-model:value="agentConfig.retrievalLimit"
                    :min="1"
                    :max="100"
                    style="width: 100%"
                  />
                </a-form-item>
              </a-col>
            </a-row>
            <a-row>
              <a-col :span="24">
                <a-form-item label="Thinking模式">
                  <a-switch v-model:checked="agentConfig.useThinking" />
                </a-form-item>
              </a-col>
            </a-row>
          </a-form>
        </div>

        <!-- 底部输入区 -->
        <div class="qa-panel-footer">
          <div class="chat-input-container">
            <!-- 第一行：文本输入区域 -->
            <a-textarea
              v-model:value="chatInput"
              :rows="3"
              :placeholder="chatMode === 'conversation' ? '输入你的问题...（系统会自动从该知识库的文档中检索相关信息）' : '描述你的需求或问题，系统会根据检索到的相关内容生成需求文档...'"
              @pressEnter="handleSendMessage"
              :disabled="chatLoading"
              style="width: 100%; margin-bottom: 8px"
            />
            <!-- 第二行：4个控件 -->
            <div class="chat-controls-row">
              <div class="chat-controls-left">
                <a-select
                  v-model:value="chatMode"
                  style="width: 120px; margin-right: 8px"
                  size="small"
                  @change="handleChatModeChange"
                >
                  <a-select-option value="conversation">对话模式</a-select-option>
                  <a-select-option value="agent">Agent模式</a-select-option>
                </a-select>
                <a-button
                  v-if="chatMode === 'agent'"
                  type="text"
                  size="small"
                  @click="handleOpenAgentSettings"
                  style="margin-right: 8px; padding: 0 4px"
                  title="Agent模式设置"
                >
                  <SettingOutlined />
                </a-button>
                <a-button
                  v-if="chatMode === 'conversation'"
                  type="text"
                  size="small"
                  @click="showRetrievalSettings = true"
                  style="margin-right: 8px; padding: 0 4px"
                  title="检索设置"
                >
                  <SettingOutlined />
                </a-button>
                <a-select
                  v-model:value="chatModel"
                  style="width: 120px; margin-right: 8px"
                  size="small"
                >
                  <a-select-option value="local">本地大模型</a-select-option>
                </a-select>
                <a-button 
                  @click="handleClearChat"
                  size="small"
                >
                  清空对话
                </a-button>
              </div>
              <a-button 
                type="primary" 
                @click="handleSendMessage" 
                :loading="chatLoading" 
                :disabled="!chatInput.trim() || kbDocumentGroupIds.length === 0"
                size="small"
              >
                <template #icon><SendOutlined /></template>
                发送
              </a-button>
            </div>
          </div>
        </div>
      </div>
    </a-layout-sider>
  </a-layout>

  <!-- Agent模式设置模态框 -->
  <a-modal
    v-model:open="agentSettingsModalVisible"
    title="Agent模式设置"
    :width="600"
    @ok="handleSaveAgentSettings"
    @cancel="handleCancelAgentSettings"
  >
    <a-form :label-col="{ span: 6 }" :wrapper-col="{ span: 18 }" size="default">
      <a-form-item label="最大迭代次数">
        <a-input-number
          v-model:value="agentSettingsForm.maxIterations"
          :min="1"
          :max="10"
          style="width: 100%"
        />
      </a-form-item>
      <a-form-item label="检索数量">
        <a-input-number
          v-model:value="agentSettingsForm.retrievalLimit"
          :min="1"
          :max="100"
          style="width: 100%"
        />
      </a-form-item>
      <a-form-item label="质量阈值">
        <a-slider
          v-model:value="agentSettingsForm.qualityThreshold"
          :min="0"
          :max="100"
        />
        <div style="text-align: center; margin-top: 8px; color: #8c8c8c">
          {{ agentSettingsForm.qualityThreshold }}
        </div>
      </a-form-item>
      <a-form-item label="Thinking模式">
        <a-switch v-model:checked="agentSettingsForm.useThinking" />
      </a-form-item>
    </a-form>
  </a-modal>

  <!-- 查看解析结果模态框 -->
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
              <a-button size="small" type="primary" ghost @click="downloadParseFile('parsed')">
                <template #icon><DownloadOutlined /></template>
                下载
              </a-button>
            </div>
            <div 
              style="background: #f5f5f5; padding: 16px; border-radius: 4px; max-height: calc(100vh - 340px); overflow-y: auto; font-family: 'Microsoft YaHei', sans-serif; font-size: 14px; line-height: 1.8;"
              v-html="formatParseMarkdown(parsedContentText, `upload_${parsedContentModalData?.id}`, parsedContentModalData?.id)"
            ></div>
          </div>
          <a-empty v-else description="完整对应文档不可用" />
        </a-tab-pane>
        
        <!-- Tab 2: 总结文档 -->
        <a-tab-pane key="summary" tab="总结文档">
          <div v-if="summaryContentText">
            <div style="display: flex; justify-content: flex-end; margin-bottom: 8px;">
              <a-button size="small" type="primary" ghost @click="downloadParseFile('summary')">
                <template #icon><DownloadOutlined /></template>
                下载
              </a-button>
            </div>
            <div 
              style="background: #f5f5f5; padding: 16px; border-radius: 4px; max-height: calc(100vh - 340px); overflow-y: auto; font-family: 'Microsoft YaHei', sans-serif; font-size: 14px; line-height: 1.8;"
              v-html="formatParseMarkdown(summaryContentText, `upload_${parsedContentModalData?.id}`, parsedContentModalData?.id)"
            ></div>
          </div>
          <a-empty v-else description="总结文档不可用" />
        </a-tab-pane>
        
        <!-- Tab 3: 结构化数据 -->
        <a-tab-pane key="structured" tab="结构化数据">
          <div v-if="structuredContentText">
            <div style="display: flex; justify-content: flex-end; margin-bottom: 8px;">
              <a-button size="small" type="primary" ghost @click="downloadParseFile('structured')">
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
              <a-button size="small" type="primary" ghost @click="downloadParseFile('chunks')">
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
          <a-empty v-else description="分块结果不可用（请先执行分块）" />
        </a-tab-pane>
      </a-tabs>
      <a-empty v-else description="正在加载解析结果..." />
    </a-spin>
  </a-modal>
  
  <!-- 对话模式检索设置弹窗 -->
  <RetrievalSettingsModal
    v-model:open="showRetrievalSettings"
    :settings="retrievalSettings"
    :support-thinking="chatModel === 'local'"
    @confirm="handleRetrievalSettingsConfirm"
  />
  
  <!-- 检索结果详情模态框 -->
  <a-modal
    v-model:open="detailModalVisible"
    :title="detailModalTitle"
    width="1000px"
    :footer="null"
    :maskClosable="true"
  >
    <div v-if="selectedRetrievalItem" style="max-height: 70vh; overflow-y: auto;">
      <a-descriptions :column="2" bordered>
        <a-descriptions-item label="类型" :span="2">
          <a-tag :color="getDetailTypeColor(selectedRetrievalItem.type)">
            {{ getDetailTypeLabel(selectedRetrievalItem.type) }}
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="相似度" :span="2" v-if="selectedRetrievalItem.score">
          {{ selectedRetrievalItem.score.toFixed(1) }}%
        </a-descriptions-item>
        
        <!-- Community详情 -->
        <template v-if="selectedRetrievalItem.type === 'community'">
          <a-descriptions-item label="名称" :span="2">
            {{ selectedRetrievalItem.properties?.name || '未知' }}
          </a-descriptions-item>
          <a-descriptions-item label="摘要" :span="2" v-if="selectedRetrievalItem.properties?.summary">
            {{ selectedRetrievalItem.properties.summary }}
          </a-descriptions-item>
          <a-descriptions-item label="成员数量" v-if="selectedRetrievalItem.properties?.member_count !== undefined">
            {{ selectedRetrievalItem.properties.member_count }}
          </a-descriptions-item>
          <a-descriptions-item label="Group ID" v-if="selectedRetrievalItem.properties?.group_id">
            {{ selectedRetrievalItem.properties.group_id }}
          </a-descriptions-item>
          <a-descriptions-item label="成员列表" :span="2" v-if="selectedRetrievalItem.properties?.member_names && selectedRetrievalItem.properties.member_names.length > 0">
            {{ selectedRetrievalItem.properties.member_names.join(', ') }}
          </a-descriptions-item>
        </template>

        <!-- Episode详情 -->
        <template v-if="selectedRetrievalItem.type === 'episode'">
          <a-descriptions-item label="名称" :span="2">
            {{ selectedRetrievalItem.properties?.name || '未知' }}
          </a-descriptions-item>
          <a-descriptions-item label="来源" v-if="selectedRetrievalItem.properties?.source_description">
            {{ selectedRetrievalItem.properties.source_description }}
          </a-descriptions-item>
          <a-descriptions-item label="Group ID" v-if="selectedRetrievalItem.properties?.group_id">
            {{ selectedRetrievalItem.properties.group_id }}
          </a-descriptions-item>
          <!-- 图片预览（如果是图片Episode） -->
          <a-descriptions-item label="图片预览" :span="2" v-if="episodeImageInfo">
            <div style="text-align: center; padding: 16px; background: #f5f5f5; border-radius: 4px;">
              <img 
                :src="episodeImageInfo.url" 
                :alt="episodeImageInfo.description"
                style="max-width: 100%; max-height: 500px; border: 1px solid #d9d9d9; border-radius: 4px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);"
                @error="handleImageError"
              />
              <div style="margin-top: 8px; color: #666; font-size: 12px;">
                {{ episodeImageInfo.description }}
              </div>
            </div>
          </a-descriptions-item>
          <a-descriptions-item label="完整内容" :span="2" v-if="selectedRetrievalItem.properties?.content">
            <div 
              v-html="formatRetrievalMarkdown(selectedRetrievalItem.properties.content)"
              style="font-family: 'Microsoft YaHei', sans-serif; font-size: 14px; line-height: 1.8; background: #f5f5f5; padding: 16px; border-radius: 4px; max-height: 400px; overflow-y: auto;"
            ></div>
          </a-descriptions-item>
        </template>

        <!-- Edge（关系）详情 -->
        <template v-if="selectedRetrievalItem.type === 'edge'">
          <a-descriptions-item label="关系类型" :span="2">
            <a-tag color="blue">{{ selectedRetrievalItem.rel_type || selectedRetrievalItem.type }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="源节点" :span="2">
            {{ selectedRetrievalItem.source_name || `节点${selectedRetrievalItem.source}` }}
          </a-descriptions-item>
          <a-descriptions-item label="目标节点" :span="2">
            {{ selectedRetrievalItem.target_name || `节点${selectedRetrievalItem.target}` }}
          </a-descriptions-item>
          <a-descriptions-item label="关系描述" :span="2" v-if="selectedRetrievalItem.fact">
            {{ selectedRetrievalItem.fact }}
          </a-descriptions-item>
          <a-descriptions-item label="Group ID" v-if="selectedRetrievalItem.properties?.group_id">
            {{ selectedRetrievalItem.properties.group_id }}
          </a-descriptions-item>
          <a-descriptions-item label="UUID" v-if="selectedRetrievalItem.id">
            {{ selectedRetrievalItem.id }}
          </a-descriptions-item>
        </template>

        <!-- Entity详情 -->
        <template v-if="selectedRetrievalItem.type === 'entity' || selectedRetrievalItem.type === 'node'">
          <a-descriptions-item label="名称" :span="2">
            {{ selectedRetrievalItem.properties?.name || '未知' }}
          </a-descriptions-item>
          <a-descriptions-item label="类型" :span="2">
            <a-tag :color="getTypeColor(selectedRetrievalItem.labels?.[0])">
              {{ selectedRetrievalItem.labels?.[0] || 'Entity' }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="摘要" :span="2" v-if="selectedRetrievalItem.properties?.summary">
            {{ selectedRetrievalItem.properties.summary }}
          </a-descriptions-item>
          <a-descriptions-item label="Group ID" v-if="selectedRetrievalItem.properties?.group_id">
            {{ selectedRetrievalItem.properties.group_id }}
          </a-descriptions-item>
          <a-descriptions-item label="UUID" v-if="selectedRetrievalItem.id">
            {{ selectedRetrievalItem.id }}
          </a-descriptions-item>
        </template>

        <!-- 其他属性 -->
        <a-descriptions-item label="完整属性" :span="2" v-if="selectedRetrievalItem.properties">
          <pre style="background: #f5f5f5; padding: 12px; border-radius: 4px; overflow-x: auto; max-height: 300px; overflow-y: auto; font-size: 12px;">{{ formatRetrievalProperties(selectedRetrievalItem.properties) }}</pre>
        </a-descriptions-item>
      </a-descriptions>
    </div>
  </a-modal>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import {
  FolderOutlined,
  TeamOutlined,
  EditOutlined,
  DeleteOutlined,
  UnorderedListOutlined,
  DownloadOutlined,
  FileTextOutlined,
  SendOutlined,
  BookOutlined,
  DatabaseOutlined,
  RocketOutlined,
  BulbOutlined,
  CodeOutlined,
  BankOutlined,
  MedicineBoxOutlined,
  SafetyOutlined,
  ReadOutlined,
  HomeOutlined,
  ShareAltOutlined,
  MessageOutlined,
  PlusOutlined,
  CaretRightOutlined,
  ArrowRightOutlined,
  LoadingOutlined,
  SettingOutlined,
  LogoutOutlined,
  EyeOutlined,
  ReloadOutlined
} from '@ant-design/icons-vue'
import RetrievalSettingsModal from '../components/RetrievalSettingsModal.vue'
import {
  getKnowledgeBases,
  getKnowledgeBase,
  updateKnowledgeBase,
  deleteKnowledgeBase,
  createKnowledgeBase,
  addDocumentsFromLibrary,
  getKnowledgeBaseDocuments,
  deleteKnowledgeBaseDocument,
  shareKnowledgeBaseToAll,
  leaveKnowledgeBase
} from '@/api/knowledgeBase'
import { getDocuments as getLibraryDocuments } from '@/api/documentLibrary'
import {
  getParsedContent,
  getSummaryContent,
  getStructuredContent,
  getChunks
} from '@/api/documentUpload'
import { qaChat, generateRequirementDocumentAsync, getChatHistory } from '@/api/requirements'
import { getUser, isAdmin as checkIsAdmin } from '@/utils/auth'

const route = useRoute()
const router = useRouter()
const currentUser = ref(getUser())

const loading = ref(false)
const selectedKbId = ref(null)
const selectedKB = ref(null)
const privateKBs = ref([]) // 个人知识库（visibility='private'）
const myCreatedSharedKBs = ref([]) // 共享知识库中我创建的（visibility='shared'，creator_name=当前用户）
const myJoinedSharedKBs = ref([]) // 共享知识库中我加入的（visibility='shared'，已加入但不是创建者）
const sharedCollapseKeys = ref(['my_created_shared', 'my_joined_shared'])

const description = ref('')
const searchKeyword = ref('')
const documents = ref([])
const documentsLoading = ref(false)
const documentsPagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0
})

const chatMessages = ref([])
const chatInput = ref('')
const chatLoading = ref(false)
const chatMessagesRef = ref(null)
const chatMode = ref('conversation')
const chatModel = ref('local')

// Mem0 session_id 管理
const getSessionId = () => {
  if (!selectedKB.value) return null
  const key = `mem0_session_id_${selectedKB.value.id}`
  let sessionId = localStorage.getItem(key)
  if (!sessionId) {
    // 生成简单的 UUID（如果浏览器支持 crypto.randomUUID，使用它；否则使用时间戳+随机数）
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
      sessionId = crypto.randomUUID()
    } else {
      sessionId = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
    }
    localStorage.setItem(key, sessionId)
  }
  return sessionId
}

// Agent模式配置
const agentConfig = reactive({
  maxIterations: 3,
  qualityThreshold: 80,
  retrievalLimit: 20,
  useThinking: false
})

// Agent设置模态框
const agentSettingsModalVisible = ref(false)
const agentSettingsForm = reactive({
  maxIterations: 3,
  qualityThreshold: 80,
  retrievalLimit: 20,
  useThinking: false
})

// 对话模式检索设置
const showRetrievalSettings = ref(false)
const retrievalSettings = ref({
  scheme: 'default',
  limit: 20,
  simThreshold: 60,
  useThinking: false,
  truncateLength: 500,
  summaryLength: 200
})

// 知识库文档的group_ids（用于API调用）
const kbDocumentGroupIds = ref([])

// 删除文档相关
const deletingDocumentId = ref(null)

// 查看解析结果模态框相关
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

// 创建知识库相关
const createModalVisible = ref(false)
const createForm = reactive({
  name: '',
  description: '',
  visibility: 'private'
})
const createFormRef = ref(null)

// 编辑知识库相关
const editModalVisible = ref(false)
const editForm = reactive({
  name: '',
  description: '',
  visibility: 'private'
})
const editFormRef = ref(null)

// 从文档库选择文档相关
const showDocumentLibraryModal = ref(false)
const libraryDocuments = ref([])
const libraryDocumentsLoading = ref(false)
const libraryDocumentsPage = ref(1)
const libraryDocumentsPageSize = ref(10)
const libraryDocumentsTotal = ref(0)
const librarySearchKeyword = ref('')
const selectedLibraryDocuments = ref([])
const addingDocuments = ref(false)
const libraryDocumentColumns = [
  {
    title: '文档名称',
    dataIndex: 'original_name',
    key: 'original_name',
    ellipsis: true
  },
  {
    title: '状态',
    key: 'status',
    width: 100
  },
  {
    title: '文件大小',
    key: 'file_size',
    width: 100
  },
  {
    title: '上传时间',
    key: 'created_at',
    width: 180
  }
]
const addDocumentConfig = reactive({
  chunk_strategy: 'auto',
  max_tokens_per_section: 8000,
  analysis_mode: 'smart_segment',
  provider: 'local',
  use_thinking: false
})

// 列宽调整（默认比例：第一列窄，第二列中等，第三列最宽）
// 使用固定宽度实现比例
const leftSiderWidth = ref(240) // 第一列：240px（最窄）
const rightSiderWidth = ref(null) // 第三列：使用flex: 2（最宽）
const isResizing = ref(false)
const resizeType = ref(null) // 'left' or 'right'
const startX = ref(0)
const startLeftWidth = ref(0)
const startRightWidth = ref(0)

// 初始化拖拽起始位置
const initResize = (e) => {
  startX.value = e.clientX
}

// 开始调整大小
const startResize = (type) => {
  isResizing.value = true
  resizeType.value = type
  
  // 获取当前实际宽度
  const leftSider = document.querySelector('.left-sider')
  const rightSider = document.querySelector('.right-sider')
  
  if (type === 'left' && leftSider) {
    startLeftWidth.value = leftSider.offsetWidth
    leftSiderWidth.value = leftSider.offsetWidth // 转换为固定宽度
  } else if (type === 'right' && rightSider) {
    startRightWidth.value = rightSider.offsetWidth
    rightSiderWidth.value = rightSider.offsetWidth // 转换为固定宽度
  }
  
  document.addEventListener('mousemove', handleResize)
  document.addEventListener('mouseup', stopResize)
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
}

// 调整大小
const handleResize = (e) => {
  if (!isResizing.value) return
  
  const deltaX = e.clientX - startX.value
  
  if (resizeType.value === 'left') {
    const newWidth = startLeftWidth.value + deltaX
    if (newWidth >= 200 && newWidth <= 500) {
      leftSiderWidth.value = newWidth
    }
  } else {
    const newWidth = startRightWidth.value - deltaX
    if (newWidth >= 300 && newWidth <= 800) {
      rightSiderWidth.value = newWidth
    }
  }
}

// 停止调整大小
const stopResize = () => {
  isResizing.value = false
  resizeType.value = null
  document.removeEventListener('mousemove', handleResize)
  document.removeEventListener('mouseup', stopResize)
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
}

// 图标映射
const iconMap = {
  'folder': FolderOutlined,
  'book': BookOutlined,
  'file': FileTextOutlined,
  'database': DatabaseOutlined,
  'team': TeamOutlined,
  'rocket': RocketOutlined,
  'bulb': BulbOutlined,
  'code': CodeOutlined,
  'bank': BankOutlined,
  'medicine': MedicineBoxOutlined,
  'safety': SafetyOutlined,
  'read': ReadOutlined,
  'home': HomeOutlined
}

const getIconComponent = (iconName) => {
  return iconMap[iconName] || FolderOutlined
}

const isOwner = computed(() => {
  if (!selectedKB.value || !currentUser.value) return false
  return selectedKB.value.creator_name === currentUser.value.username
})

const isEditor = computed(() => {
  if (!selectedKB.value || !currentUser.value) return false
  // 如果是创建者，也是编辑者
  if (selectedKB.value.creator_name === currentUser.value.username) return true
  // 检查用户角色
  return selectedKB.value.user_role === 'editor' || selectedKB.value.user_role === 'admin'
})

const isAdminUser = computed(() => {
  return currentUser.value && checkIsAdmin()
})

const isMember = computed(() => {
  if (!selectedKB.value || !currentUser.value) return false
  // 如果是创建者，不是成员（成员指的是非创建者的加入者）
  if (selectedKB.value.creator_name === currentUser.value.username) return false
  // 检查是否是成员（通过 user_role 或 is_member 字段判断）
  return selectedKB.value.user_role !== undefined || selectedKB.value.is_member === true
})

// 加载知识库列表
const loadKnowledgeBases = async () => {
  loading.value = true
  try {
    // 加载所有我创建的知识库
    const createdRes = await getKnowledgeBases({ filter_type: 'my_created' })
    const allMyCreated = createdRes.knowledge_bases || []
    
    // 分离个人知识库和共享知识库（我创建的）
    privateKBs.value = allMyCreated.filter(kb => kb.visibility === 'private')
    myCreatedSharedKBs.value = allMyCreated.filter(kb => kb.visibility === 'shared')

    // 加载我加入的知识库（只包含共享知识库）
    const joinedRes = await getKnowledgeBases({ filter_type: 'my_joined' })
    myJoinedSharedKBs.value = (joinedRes.knowledge_bases || []).filter(kb => kb.visibility === 'shared')

    // 如果有路由参数，选择对应的知识库
    if (route.params.id) {
      selectKnowledgeBase(parseInt(route.params.id))
    } else {
      // 默认选择第一个可用的知识库（优先：个人 > 共享-我创建的 > 共享-我加入的）
      if (privateKBs.value.length > 0) {
        selectKnowledgeBase(privateKBs.value[0].id)
      } else if (myCreatedSharedKBs.value.length > 0) {
        selectKnowledgeBase(myCreatedSharedKBs.value[0].id)
      } else if (myJoinedSharedKBs.value.length > 0) {
        selectKnowledgeBase(myJoinedSharedKBs.value[0].id)
      }
    }
  } catch (error) {
    message.error('加载知识库列表失败: ' + (error.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

// 选择知识库
const selectKnowledgeBase = async (kbId) => {
  selectedKbId.value = kbId
  loading.value = true
  
  try {
    await loadSelectedKB()
  } catch (error) {
    message.error('加载知识库详情失败: ' + (error.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

// 加载选中的知识库详情
const loadSelectedKB = async () => {
  if (!selectedKbId.value) return
  
  try {
    const kb = await getKnowledgeBase(selectedKbId.value)
    selectedKB.value = kb
    
    // 加载描述
    description.value = kb.description || ''
    
    // 加载文档列表（loadDocuments 内部已经处理了 kbDocumentGroupIds 的加载）
    await loadDocuments()
  } catch (error) {
    console.error('加载知识库详情失败:', error)
    throw error
  }
}

// 加载文档列表
const loadDocuments = async () => {
  if (!selectedKB.value) {
    console.log('loadDocuments: selectedKB.value is null')
    return
  }
  
  console.log('loadDocuments: 开始加载文档，知识库ID:', selectedKB.value.id)
  documentsLoading.value = true
  try {
    // 加载文档列表（分页）
    const res = await getKnowledgeBaseDocuments(selectedKB.value.id, {
      page: documentsPagination.current,
      page_size: documentsPagination.pageSize,
      search: searchKeyword.value || undefined
    })
    console.log('loadDocuments: API响应:', res)
    documents.value = res.documents || []
    documentsPagination.total = res.total || 0
    console.log('loadDocuments: 文档数量:', documents.value.length, '总数:', documentsPagination.total)
    
    // 提取所有已完成的文档的document_id（group_id）
    // 为了获取所有已完成的文档用于聊天，需要分页加载所有文档
    const allCompletedDocumentIds = []
    if (res.total > 0) {
      // 分页加载所有文档以获取所有已完成的文档ID
      const totalPages = Math.ceil(res.total / 100) // 后端限制最大100
      for (let page = 1; page <= totalPages; page++) {
        const pageRes = await getKnowledgeBaseDocuments(selectedKB.value.id, {
          page: page,
          page_size: 100, // 使用最大允许值
          search: searchKeyword.value || undefined
        })
        const completedIds = (pageRes.documents || [])
          .filter(doc => doc.status === 'completed' && doc.document_id)
          .map(doc => doc.document_id)
        allCompletedDocumentIds.push(...completedIds)
      }
    }
    
    kbDocumentGroupIds.value = allCompletedDocumentIds
    console.log('loadDocuments: 已完成的文档group_ids:', kbDocumentGroupIds.value)
  } catch (error) {
    console.error('loadDocuments: 加载失败:', error)
    message.error('加载文档列表失败: ' + (error.message || '未知错误'))
    documents.value = []
    documentsPagination.total = 0
    kbDocumentGroupIds.value = []
  } finally {
    documentsLoading.value = false
  }
}

// 更新描述
const handleUpdateDescription = async () => {
  if (!selectedKB.value || !isOwner.value) return
  
  try {
    await updateKnowledgeBase(selectedKB.value.id, {
      description: description.value
    })
    message.success('更新成功')
    selectedKB.value.description = description.value
  } catch (error) {
    message.error('更新失败: ' + (error.message || '未知错误'))
  }
}

// 编辑
const handleEdit = () => {
  if (!selectedKB.value) return
  
  editForm.name = selectedKB.value.name
  editForm.description = selectedKB.value.description || ''
  editForm.visibility = selectedKB.value.visibility || 'private'
  editModalVisible.value = true
}

// 确认编辑
const handleEditConfirm = async () => {
  if (!selectedKB.value) return
  
  try {
    await editFormRef.value.validate()
    
    await updateKnowledgeBase(selectedKB.value.id, {
      name: editForm.name,
      description: editForm.description,
      visibility: editForm.visibility
    })
    
    message.success('更新成功')
    editModalVisible.value = false
    
    // 重新加载知识库列表和当前知识库
    await loadKnowledgeBases()
    await loadSelectedKB()
  } catch (error) {
    if (error.errorFields) {
      // 表单验证错误
      return
    }
    message.error('更新失败: ' + (error.message || '未知错误'))
  }
}

// 取消编辑
const handleEditCancel = () => {
  editModalVisible.value = false
  editForm.name = ''
  editForm.description = ''
  editForm.visibility = 'private'
}

// 检索设置确认
const handleRetrievalSettingsConfirm = (settings) => {
  retrievalSettings.value = settings
  // 保存到本地存储
  localStorage.setItem('retrievalSettings', JSON.stringify(settings))
}

// 检索结果详情相关
const selectedRetrievalItem = ref(null)
const detailModalVisible = ref(false)
const detailModalTitle = computed(() => {
  if (!selectedRetrievalItem.value) return '检索结果详情'
  const type = selectedRetrievalItem.value.type
  const typeLabel = getDetailTypeLabel(type)
  const name = selectedRetrievalItem.value.properties?.name || 
               selectedRetrievalItem.value.source_name || 
               '未知'
  return `${typeLabel}详情 - ${name}`
})

const handleViewRetrievalDetail = (item) => {
  selectedRetrievalItem.value = item
  detailModalVisible.value = true
}

// 判断Episode是否是图片类型
const isImageEpisode = computed(() => {
  if (!selectedRetrievalItem.value || selectedRetrievalItem.value.type !== 'episode') {
    return false
  }
  const name = selectedRetrievalItem.value.properties?.name || ''
  return name.includes('图片') || name.includes('_图片_') || name.match(/图片\s*\d+/)
})

// 从Episode中提取图片信息
const episodeImageInfo = computed(() => {
  if (!isImageEpisode.value || !selectedRetrievalItem.value) {
    return null
  }
  
  const props = selectedRetrievalItem.value.properties || {}
  const name = props.name || ''
  const groupId = props.group_id || ''
  
  // 从名称中提取图片编号（支持多种格式：_图片_1_、_图片1_、图片 1等）
  let imageNumber = null
  const patterns = [
    /图片[_\s]*(\d+)/,  // 匹配：图片_1、图片1、图片 1
    /_图片[_\s]*(\d+)_/,  // 匹配：_图片_1_
    /图片[_\s]*(\d+)[_\s]/,  // 匹配：图片_1_、图片1_
  ]
  
  for (const pattern of patterns) {
    const match = name.match(pattern)
    if (match && match[1]) {
      imageNumber = match[1]
      break
    }
  }
  
  if (!imageNumber) {
    return null
  }
  
  // 从group_id中提取upload_id（格式：..._23，最后一部分是upload_id）
  let uploadId = null
  if (groupId) {
    const parts = groupId.split('_')
    if (parts.length > 0) {
      const lastPart = parts[parts.length - 1]
      // 检查最后一部分是否是数字
      if (/^\d+$/.test(lastPart)) {
        uploadId = parseInt(lastPart)
      } else {
        // 如果不是纯数字，尝试从倒数第二部分获取
        if (parts.length > 1) {
          const secondLastPart = parts[parts.length - 2]
          if (/^\d+$/.test(secondLastPart)) {
            uploadId = parseInt(secondLastPart)
          }
        }
      }
    }
  }
  
  if (!uploadId) {
    return null
  }
  
  // 构建图片URL
  const imageId = `image_${imageNumber}`
  const imageUrl = `/api/document-upload/${uploadId}/images/${imageId}`
  
  // 提取描述（从名称中，格式：..._图片_1_描述）
  let description = `图片 ${imageNumber}`
  const descMatch = name.match(/图片[_\s]*\d+[_\s]*(.+)/)
  if (descMatch && descMatch[1]) {
    description = descMatch[1].trim()
  }
  
  return {
    imageId,
    imageNumber,
    uploadId,
    url: imageUrl,
    description
  }
})

// 处理图片加载错误
const handleImageError = (event) => {
  console.error('图片加载失败:', event.target.src)
  // 可以显示一个占位符或错误提示
  event.target.style.display = 'none'
}

const getDetailTypeLabel = (type) => {
  const typeMap = {
    'community': 'Community',
    'episode': 'Episode',
    'edge': '关系',
    'entity': '实体',
    'node': '实体'
  }
  return typeMap[type] || type
}

const getDetailTypeColor = (type) => {
  const colorMap = {
    'community': 'purple',
    'episode': 'purple',
    'edge': 'blue',
    'entity': 'green',
    'node': 'green'
  }
  return colorMap[type] || 'default'
}

// 格式化属性为JSON字符串（用于检索结果详情）
const formatRetrievalProperties = (properties) => {
  if (!properties) return ''
  try {
    // 过滤掉不需要显示的字段
    const filtered = { ...properties }
    delete filtered.name_embedding // 不显示embedding向量
    
    return JSON.stringify(filtered, null, 2)
  } catch (e) {
    return String(properties)
  }
}

// 格式化Markdown内容为HTML（用于检索结果详情）
const formatRetrievalMarkdown = (text) => {
  if (!text) return ''
  
  // 转义HTML特殊字符（除了我们需要的标签）
  const escapeHtml = (str) => {
    const div = document.createElement('div')
    div.textContent = str
    return div.innerHTML
  }
  
  // 1. 处理Markdown表格
  const tableRegex = /(\|.+\|(?:\s*\n\s*\|[:\-\s\|]+\|)?(?:\s*\n\s*\|.+\|)+)/g
  let processedText = text.replace(tableRegex, (match) => {
    const lines = match.trim().split('\n').filter(line => line.trim())
    if (lines.length < 2) return match
    
    const headerLine = lines[0].trim()
    const headers = headerLine.split('|').map(h => h.trim()).filter(h => h)
    
    let dataStartIndex = 1
    if (lines[1].trim().match(/^[\|\s\-\:]+$/)) {
      dataStartIndex = 2
    }
    
    const rows = []
    for (let i = dataStartIndex; i < lines.length; i++) {
      const cells = lines[i].split('|').map(c => c.trim()).filter((c, idx) => idx > 0 && idx < lines[i].split('|').length - 1)
      if (cells.length > 0) {
        rows.push(cells)
      }
    }
    
    let htmlTable = '<table style="border-collapse: collapse; width: 100%; margin: 16px 0; border: 1px solid #d9d9d9;">'
    htmlTable += '<thead><tr style="background: #fafafa;">'
    headers.forEach(header => {
      htmlTable += `<th style="border: 1px solid #d9d9d9; padding: 8px 12px; text-align: left; font-weight: 600;">${escapeHtml(header)}</th>`
    })
    htmlTable += '</tr></thead>'
    htmlTable += '<tbody>'
    rows.forEach(row => {
      htmlTable += '<tr>'
      headers.forEach((_, colIndex) => {
        const cellContent = row[colIndex] || ''
        htmlTable += `<td style="border: 1px solid #d9d9d9; padding: 8px 12px;">${escapeHtml(cellContent)}</td>`
      })
      htmlTable += '</tr>'
    })
    htmlTable += '</tbody></table>'
    
    return htmlTable
  })
  
  // 2. 处理Markdown图片
  processedText = processedText.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, alt, url) => {
    if (url.includes('/images/') || url.startsWith('/api/document-upload/') || url.startsWith('/api/word-document/')) {
      const linkText = alt || '图片'
      return `<a href="${url}" target="_blank" style="color: #1890ff; cursor: pointer; text-decoration: underline; display: inline-block; margin: 8px 0;">
        <img src="${url}" alt="${escapeHtml(linkText)}" style="max-width: 100%; height: auto; border: 1px solid #d9d9d9; border-radius: 4px; padding: 4px; background: #fafafa;" 
        onerror="this.style.display='none'; this.nextElementSibling.style.display='inline';">
        <span style="display: none;">${escapeHtml(linkText)}</span>
      </a>`
    }
    return `<img src="${url}" alt="${escapeHtml(alt || '')}" style="max-width: 100%; height: auto; margin: 8px 0;">`
  })
  
  // 3. 处理Markdown链接
  processedText = processedText.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, linkText, url) => {
    if (match.includes('<img')) return match
    return `<a href="${url}" target="_blank" style="color: #1890ff; text-decoration: underline;">${escapeHtml(linkText)}</a>`
  })
  
  // 4. 处理标题
  processedText = processedText.replace(/^#### (.*$)/gim, '<h4 style="margin: 16px 0 8px 0; font-size: 16px; font-weight: 600;">$1</h4>')
  processedText = processedText.replace(/^### (.*$)/gim, '<h3 style="margin: 20px 0 12px 0; font-size: 18px; font-weight: 600;">$1</h3>')
  processedText = processedText.replace(/^## (.*$)/gim, '<h2 style="margin: 24px 0 16px 0; font-size: 20px; font-weight: 600;">$1</h2>')
  processedText = processedText.replace(/^# (.*$)/gim, '<h1 style="margin: 28px 0 20px 0; font-size: 24px; font-weight: 600;">$1</h1>')
  
  // 5. 处理粗体
  processedText = processedText.replace(/\*\*([^\*]+)\*\*/g, '<strong>$1</strong>')
  
  // 6. 处理斜体
  processedText = processedText.replace(/\*([^\*]+)\*/g, '<em>$1</em>')
  
  // 7. 处理代码块
  processedText = processedText.replace(/```([^`]+)```/g, '<pre style="background: #f5f5f5; padding: 12px; border-radius: 4px; overflow-x: auto; margin: 12px 0;"><code>$1</code></pre>')
  
  // 8. 处理行内代码
  processedText = processedText.replace(/`([^`]+)`/g, '<code style="background: #f5f5f5; padding: 2px 6px; border-radius: 3px; font-family: monospace;">$1</code>')
  
  // 9. 处理列表项
  processedText = processedText.replace(/^[\-\*\+] (.+)$/gim, '<li style="margin: 4px 0;">$1</li>')
  processedText = processedText.replace(/(<li[^>]*>.*?<\/li>(?:\s*<li[^>]*>.*?<\/li>)*)/gs, '<ul style="margin: 8px 0; padding-left: 24px;">$1</ul>')
  
  // 10. 处理换行
  processedText = processedText.replace(/\n\n/g, '<br><br>')
  processedText = processedText.replace(/\n/g, '<br>')
  
  return processedText
}

// 删除
const handleDelete = () => {
  if (!selectedKB.value || !isOwner.value) return
  
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除知识库"${selectedKB.value.name}"吗？此操作将同时删除知识库中的所有文档、成员和相关数据，且不可恢复。`,
    okText: '确定删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      try {
        await deleteKnowledgeBase(selectedKB.value.id)
        message.success('删除成功')
        loadKnowledgeBases()
        selectedKB.value = null
        selectedKbId.value = null
      } catch (error) {
        message.error('删除失败: ' + (error.message || '未知错误'))
      }
    }
  })
}

// 下载
const handleDownload = () => {
  message.info('下载功能待实现')
}

// 一键共享
const handleShareToAll = () => {
  if (!selectedKB.value || !isAdminUser.value) return
  
  Modal.confirm({
    title: '一键共享',
    content: '将向所有激活用户发送加入邀请（默认角色：查看者），确认继续？',
    okText: '确认',
    cancelText: '取消',
    onOk: async () => {
      try {
        const res = await shareKnowledgeBaseToAll(selectedKB.value.id)
        const { success_count, skipped_count, total_users } = res
        
        let resultMsg = `成功邀请 ${success_count} 名用户加入`
        if (skipped_count > 0) {
          resultMsg += `，${skipped_count} 名用户已存在（已跳过）`
        }
        resultMsg += `（共 ${total_users} 名激活用户）`
        
        message.success(resultMsg)
        
        // 重新加载知识库信息以更新成员数量
        await loadSelectedKB()
      } catch (error) {
        let errorMsg = '一键共享失败'
        if (error.response?.data?.detail) {
          if (Array.isArray(error.response.data.detail)) {
            errorMsg += ': ' + error.response.data.detail.map(err => err.msg).join('; ')
          } else {
            errorMsg += ': ' + error.response.data.detail
          }
        } else if (error.message) {
          errorMsg += ': ' + error.message
        }
        message.error(errorMsg)
      }
    }
  })
}

// 加载文档库文档列表
const loadLibraryDocuments = async () => {
  libraryDocumentsLoading.value = true
  try {
    const response = await getLibraryDocuments({
      page: libraryDocumentsPage.value,
      page_size: libraryDocumentsPageSize.value,
      search: librarySearchKeyword.value || undefined
      // 移除status过滤，显示所有文档（一个文档可以添加到多个知识库）
    })
    
    if (response && response.data) {
      libraryDocuments.value = response.data.items || []
      libraryDocumentsTotal.value = response.data.total || 0
    } else {
      libraryDocuments.value = []
      libraryDocumentsTotal.value = 0
    }
  } catch (error) {
    console.error('加载文档库文档失败:', error)
    message.error('加载文档库文档失败: ' + (error.message || '未知错误'))
    libraryDocuments.value = []
    libraryDocumentsTotal.value = 0
  } finally {
    libraryDocumentsLoading.value = false
  }
}

// 从文档库添加文档确认
const handleAddDocumentsFromLibrary = async () => {
  if (selectedLibraryDocuments.value.length === 0) {
    message.warning('请选择要添加的文档')
    return
  }
  
  if (!selectedKB.value) {
    message.warning('请先选择知识库')
    return
  }
  
  addingDocuments.value = true
  
  try {
    const response = await addDocumentsFromLibrary(
      selectedKB.value.id,
      selectedLibraryDocuments.value,
      addDocumentConfig
    )
    
    if (response && response.success) {
      message.success(response.message || `成功添加 ${selectedLibraryDocuments.value.length} 个文档，正在处理中...`)
      
      // 关闭弹窗并重置
      handleCancelDocumentLibrary()
      
      // 刷新文档列表
      setTimeout(() => {
        loadDocuments()
      }, 1000)
    } else {
      message.error('添加文档失败')
    }
  } catch (error) {
    console.error('添加文档失败:', error)
    message.error('添加文档失败: ' + (error.response?.data?.detail || error.message || '未知错误'))
  } finally {
    addingDocuments.value = false
  }
}

// 取消从文档库选择
const handleCancelDocumentLibrary = () => {
      showDocumentLibraryModal.value = false
      selectedLibraryDocuments.value = []
      librarySearchKeyword.value = ''
      libraryDocumentsPage.value = 1
    }
    

// 获取文档库文档状态文本
const getLibraryDocumentStatusText = (status) => {
  const statusMap = {
    'unassigned': '未分配',
    'assigned': '已分配',
    'processing': '处理中',
    'failed': '处理失败'
  }
  return statusMap[status] || status
}

// 获取文档库文档状态颜色
const getLibraryDocumentStatusColor = (status) => {
  const colorMap = {
    'unassigned': 'default',
    'assigned': 'blue',
    'processing': 'processing',
    'failed': 'red'
  }
  return colorMap[status] || 'default'
}

// 格式化文件大小
const formatFileSize = (bytes) => {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

// 对话模式切换
const handleChatModeChange = () => {
  // 切换模式时清空消息
  chatMessages.value = []
}

// 打开Agent设置模态框
const handleOpenAgentSettings = () => {
  // 同步当前配置到表单
  agentSettingsForm.maxIterations = agentConfig.maxIterations
  agentSettingsForm.qualityThreshold = agentConfig.qualityThreshold
  agentSettingsForm.retrievalLimit = agentConfig.retrievalLimit
  agentSettingsForm.useThinking = agentConfig.useThinking
  agentSettingsModalVisible.value = true
}

// 保存Agent设置
const handleSaveAgentSettings = () => {
  // 同步表单配置到实际配置
  agentConfig.maxIterations = agentSettingsForm.maxIterations
  agentConfig.qualityThreshold = agentSettingsForm.qualityThreshold
  agentConfig.retrievalLimit = agentSettingsForm.retrievalLimit
  agentConfig.useThinking = agentSettingsForm.useThinking
  agentSettingsModalVisible.value = false
  message.success('设置已保存')
}

// 取消Agent设置
const handleCancelAgentSettings = () => {
  agentSettingsModalVisible.value = false
}

// 退出知识库
const handleLeave = () => {
  if (!selectedKB.value || !isMember.value) return
  
  Modal.confirm({
    title: '确认退出',
    content: `确定要退出知识库"${selectedKB.value.name}"吗？退出后您将无法再访问此知识库的内容。`,
    okText: '确定退出',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      try {
        await leaveKnowledgeBase(selectedKB.value.id)
        message.success('退出成功')
        // 清空当前选择
        selectedKB.value = null
        selectedKbId.value = null
        // 重新加载知识库列表
        await loadKnowledgeBases()
      } catch (error) {
        let errorMsg = '退出失败'
        if (error.response?.data?.detail) {
          errorMsg += ': ' + error.response.data.detail
        } else if (error.message) {
          errorMsg += ': ' + error.message
        }
        message.error(errorMsg)
      }
    }
  })
}

// 发送消息
const handleSendMessage = async () => {
  if (!chatInput.value.trim() || !selectedKB.value) return
  
  // 检查是否有已完成的文档
  if (kbDocumentGroupIds.value.length === 0) {
    message.warning('知识库中暂无已完成的文档，请先上传并处理文档')
    return
  }
  
  const userMessage = chatInput.value.trim()
  chatInput.value = ''
  
  // 添加用户消息
  chatMessages.value.push({
    role: 'user',
    content: userMessage,
    timestamp: Date.now()
  })
  
  chatLoading.value = true
  
  try {
    if (chatMode.value === 'conversation') {
      // 对话模式：使用qaChat API
      const messageList = chatMessages.value.map(msg => ({
        role: msg.role,
        content: msg.content
      }))
      
      const res = await qaChat(
        null, // group_id (单文档模式不使用)
        kbDocumentGroupIds.value, // group_ids (多文档模式)
        false, // all_documents
        messageList,
        'local', // provider
        0.7, // temperature
        retrievalSettings.value.useThinking, // useThinking
        retrievalSettings.value.scheme, // crossEncoderMode (使用用户选择的方案)
        selectedKB.value?.id || null, // knowledgeBaseId (用于保存对话历史)
        getSessionId() // sessionId (用于Mem0记忆管理)
      )
      
      chatMessages.value.push({
        role: 'assistant',
        content: res.answer || res.content || '暂无回答',
        retrieval_results: res.retrieval_results,
        retrieval_count: res.retrieval_count,
        retrieval_time: res.retrieval_time,
        has_context: res.has_context,
        timestamp: Date.now()
      })
    } else if (chatMode.value === 'agent') {
      // Agent模式：使用generateRequirementDocumentAsync API
      const request = {
        user_query: userMessage,
        format: 'markdown',
        max_iterations: agentConfig.maxIterations,
        quality_threshold: agentConfig.qualityThreshold,
        retrieval_limit: agentConfig.retrievalLimit,
        use_thinking: agentConfig.useThinking,
        group_ids: kbDocumentGroupIds.value, // 传入所有文档的group_ids
        similar_requirement_ids: []
      }
      
      const res = await generateRequirementDocumentAsync(request)
      
      if (res && res.task_id) {
        chatMessages.value.push({
          role: 'assistant',
          content: `需求文档生成任务已提交，任务ID: ${res.task_id}。请前往"任务管理"页面查看进度。`,
          timestamp: Date.now()
        })
        message.success('文档生成任务已提交，请前往"任务管理"页面查看进度')
      } else {
        throw new Error('未返回任务ID')
      }
    }
    
    scrollToBottom()
  } catch (error) {
    console.error('发送消息失败:', error)
    message.error('发送消息失败: ' + (error.message || '未知错误'))
    chatMessages.value.push({
      role: 'assistant',
      content: '抱歉，处理失败：' + (error.message || '未知错误'),
      timestamp: Date.now()
    })
  } finally {
    chatLoading.value = false
  }
}

// 滚动到底部
const scrollToBottom = () => {
  nextTick(() => {
    if (chatMessagesRef.value) {
      chatMessagesRef.value.scrollTop = chatMessagesRef.value.scrollHeight
    }
  })
}

// 格式化时间
const formatTime = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

const formatDateTime = (dateTime) => {
  if (!dateTime) return ''
  const date = new Date(dateTime)
  const now = new Date()
  const diff = now - date
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))
  
  if (days === 0) {
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  } else if (days === 1) {
    return '昨天'
  } else {
    return date.toLocaleDateString('zh-CN')
  }
}

// 复制消息
const copyMessage = (content) => {
  navigator.clipboard.writeText(content).then(() => {
    message.success('已复制到剪贴板')
  })
}

// 清空对话
const handleClearChat = () => {
  chatMessages.value = []
  // 注意：不清除session_id，保持Mem0的跨会话记忆
  // 如果需要清除记忆，可以删除localStorage中的session_id
  message.success('对话已清空')
}

// 格式化Markdown内容为HTML
const formatMarkdown = (text) => {
  if (!text) return ''
  
  // 转义HTML特殊字符（除了我们需要的标签）
  const escapeHtml = (str) => {
    const div = document.createElement('div')
    div.textContent = str
    return div.innerHTML
  }
  
  // 1. 处理Markdown表格
  const tableRegex = /(\|.+\|(?:\s*\n\s*\|[:\-\s\|]+\|)?(?:\s*\n\s*\|.+\|)+)/g
  let processedText = text.replace(tableRegex, (match) => {
    const lines = match.trim().split('\n').filter(line => line.trim())
    if (lines.length < 2) return match
    
    const headerLine = lines[0].trim()
    const headers = headerLine.split('|').map(h => h.trim()).filter(h => h)
    
    let dataStartIndex = 1
    if (lines[1].trim().match(/^[\|\s\-\:]+$/)) {
      dataStartIndex = 2
    }
    
    const rows = []
    for (let i = dataStartIndex; i < lines.length; i++) {
      const cells = lines[i].split('|').map(c => c.trim()).filter((c, idx) => idx > 0 && idx < lines[i].split('|').length - 1)
      if (cells.length > 0) {
        rows.push(cells)
      }
    }
    
    let htmlTable = '<table style="border-collapse: collapse; width: 100%; margin: 16px 0; border: 1px solid #d9d9d9;">'
    htmlTable += '<thead><tr style="background: #fafafa;">'
    headers.forEach(header => {
      htmlTable += `<th style="border: 1px solid #d9d9d9; padding: 8px 12px; text-align: left; font-weight: 600;">${escapeHtml(header)}</th>`
    })
    htmlTable += '</tr></thead><tbody>'
    rows.forEach(row => {
      htmlTable += '<tr>'
      headers.forEach((_, colIndex) => {
        const cellContent = row[colIndex] || ''
        htmlTable += `<td style="border: 1px solid #d9d9d9; padding: 8px 12px;">${escapeHtml(cellContent)}</td>`
      })
      htmlTable += '</tr>'
    })
    htmlTable += '</tbody></table>'
    
    return htmlTable
  })
  
  // 2. 处理Markdown图片
  processedText = processedText.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, alt, url) => {
    if (url.includes('/images/') || url.startsWith('/api/document-upload/') || url.startsWith('/api/word-document/')) {
      const linkText = alt || '图片'
      return `<a href="${url}" target="_blank" style="color: #1890ff; cursor: pointer; text-decoration: underline; display: inline-block; margin: 8px 0;">
        <img src="${url}" alt="${escapeHtml(linkText)}" style="max-width: 100%; height: auto; border: 1px solid #d9d9d9; border-radius: 4px; padding: 4px; background: #fafafa;" 
        onerror="this.style.display='none'; this.nextElementSibling.style.display='inline';">
        <span style="display: none;">${escapeHtml(linkText)}</span>
      </a>`
    }
    return `<img src="${url}" alt="${escapeHtml(alt || '')}" style="max-width: 100%; height: auto; margin: 8px 0;">`
  })
  
  // 3. 处理Markdown链接
  processedText = processedText.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, linkText, url) => {
    if (match.includes('<img')) return match
    return `<a href="${url}" target="_blank" style="color: #1890ff; text-decoration: underline;">${escapeHtml(linkText)}</a>`
  })
  
  // 4. 处理标题
  processedText = processedText.replace(/^#### (.*$)/gim, '<h4 style="margin: 16px 0 8px 0; font-size: 16px; font-weight: 600;">$1</h4>')
  processedText = processedText.replace(/^### (.*$)/gim, '<h3 style="margin: 20px 0 12px 0; font-size: 18px; font-weight: 600;">$1</h3>')
  processedText = processedText.replace(/^## (.*$)/gim, '<h2 style="margin: 24px 0 16px 0; font-size: 20px; font-weight: 600;">$1</h2>')
  processedText = processedText.replace(/^# (.*$)/gim, '<h1 style="margin: 28px 0 20px 0; font-size: 24px; font-weight: 600;">$1</h1>')
  
  // 5. 处理粗体和斜体
  processedText = processedText.replace(/\*\*([^\*]+)\*\*/g, '<strong>$1</strong>')
  processedText = processedText.replace(/\*([^\*]+)\*/g, '<em>$1</em>')
  
  // 6. 处理代码块
  processedText = processedText.replace(/```([^`]+)```/g, '<pre style="background: #f5f5f5; padding: 12px; border-radius: 4px; overflow-x: auto; margin: 12px 0;"><code>$1</code></pre>')
  processedText = processedText.replace(/`([^`]+)`/g, '<code style="background: #f5f5f5; padding: 2px 6px; border-radius: 3px; font-family: monospace;">$1</code>')
  
  // 7. 处理列表
  processedText = processedText.replace(/^[\-\*\+] (.+)$/gim, '<li style="margin: 4px 0;">$1</li>')
  processedText = processedText.replace(/(<li[^>]*>.*?<\/li>(?:\s*<li[^>]*>.*?<\/li>)*)/gs, '<ul style="margin: 8px 0; padding-left: 24px;">$1</ul>')
  
  // 8. 处理换行
  processedText = processedText.replace(/\n\n/g, '<br><br>')
  processedText = processedText.replace(/\n/g, '<br>')
  
  return processedText
}

// 检索结果分类函数
const getCommunities = (results) => {
  if (!results || !Array.isArray(results)) {
    return []
  }
  // 支持 type 和 source_type 两种字段名
  return results.filter((r) => r && (r.type === 'community' || r.source_type === 'community'))
}

const getEpisodes = (results) => {
  if (!results || !Array.isArray(results)) {
    return []
  }
  // 支持 type 和 source_type 两种字段名
  return results.filter((r) => r && (r.type === 'episode' || r.source_type === 'episode'))
}

const getRelationships = (results) => {
  if (!results || !Array.isArray(results)) {
    return []
  }
  // 支持 type、source_type 和 rel_type 字段
  return results.filter((r) => r && (r.type === 'edge' || r.source_type === 'edge' || r.rel_type))
}

const getEntities = (results) => {
  if (!results || !Array.isArray(results)) {
    return []
  }
  // 支持 type、source_type 和 labels 字段
  return results.filter((r) => r && (r.type === 'node' || r.type === 'entity' || r.source_type === 'entity' || r.source_type === 'node' || (r.labels && r.labels.length > 0)))
}

const getTypeColor = (type) => {
  const colors = {
    Person: 'blue',
    Organization: 'green',
    Location: 'orange',
    Concept: 'purple',
    Event: 'pink',
    Product: 'cyan',
    Technology: 'geekblue',
    Entity: 'default',
    Episodic: 'purple',
    Requirement: 'green',
    Feature: 'blue',
    Module: 'cyan',
    Community: 'purple'
  }
  return colors[type] || 'default'
}

// 创建知识库
const handleCreateKB = (defaultVisibility = 'private') => {
  createForm.name = ''
  createForm.description = ''
  createForm.visibility = defaultVisibility
  createModalVisible.value = true
}

// 确认创建知识库
const handleCreateConfirm = async () => {
  try {
    await createFormRef.value.validate()
    const res = await createKnowledgeBase({
      name: createForm.name,
      description: createForm.description,
      visibility: createForm.visibility
    })
    message.success('创建成功')
    createModalVisible.value = false
    // 重新加载知识库列表
    await loadKnowledgeBases()
    // 自动选择新创建的知识库
    if (res && res.id) {
      selectKnowledgeBase(res.id)
    }
  } catch (error) {
    if (error.errorFields) {
      // 表单验证错误
      return
    }
    message.error('创建失败: ' + (error.message || '未知错误'))
  }
}

// 查看文档解析结果
const handleViewDocument = async (document) => {
  parsedContentModalVisible.value = true
  parsedContentModalData.value = document
  parsedContentTab.value = 'parsed'
  parsedContentText.value = ''
  summaryContentText.value = ''
  structuredContentText.value = ''
  chunksContentData.value = null
  parsedContentLoading.value = true

  try {
    // 并行加载四个内容（chunks 可能不存在，单独处理错误）
    const [parsedResponse, summaryResponse, structuredResponse] = await Promise.all([
      getParsedContent(document.id),
      getSummaryContent(document.id),
      getStructuredContent(document.id)
    ])
    
    parsedContentText.value = parsedResponse.content || ''
    summaryContentText.value = summaryResponse.content || ''
    // 将 JSON 对象格式化为字符串
    structuredContentText.value = structuredResponse.content 
      ? JSON.stringify(structuredResponse.content, null, 2)
      : ''
    
    // 单独加载 chunks（可能未分块，忽略错误）
    try {
      const chunksResponse = await getChunks(document.id)
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

// 删除文档
const handleDeleteDocument = (document) => {
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除文档"${document.file_name}"吗？此操作将同时删除相关的知识图谱数据，且不可恢复。`,
    okText: '确定删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      if (!selectedKB.value) return
      
      deletingDocumentId.value = document.id
      try {
        await deleteKnowledgeBaseDocument(selectedKB.value.id, document.id)
        message.success('文档删除成功')
        // 重新加载文档列表
        await loadDocuments()
      } catch (error) {
        console.error('删除文档失败:', error)
        message.error('删除文档失败: ' + (error.message || '未知错误'))
      } finally {
        deletingDocumentId.value = null
      }
    }
  })
}

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

// 下载解析结果文件
const downloadParseFile = (type) => {
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
  
  message.success('下载成功')
}

// 格式化Markdown内容（用于解析结果查看）
const formatParseMarkdown = (text, documentId = null, uploadId = null) => {
  if (!text) return ''
  
  // 将 /api/word-document/{document_id}/ 转换为 /api/document-upload/{upload_id}/
  if (uploadId && documentId) {
    // 转换图片URL
    text = text.replace(/\/api\/word-document\/([^/]+)\/images\/([^)]+)/g, (match, docId, imageId) => {
      if (docId === documentId) {
        const newUrl = `/api/document-upload/${uploadId}/images/${imageId}`
        return newUrl
      }
      return match
    })
    
    // 转换嵌入文档URL
    text = text.replace(/\/api\/word-document\/([^/]+)\/ole\/([^?\s)]+)(\?[^)\s]*)?/g, (match, docId, oleId, query) => {
      if (docId === documentId) {
        const newUrl = `/api/document-upload/${uploadId}/ole/${oleId}${query || ''}`
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
    
    // 处理嵌入文档的特殊格式
    const embeddedDocPattern = /\[嵌入文档:\s*([^\]]+?)\s*\(([^)]+)\)\]\(([^)]+)\)\s*\n\s*\[查看\]\(([^)]+)\)\s*\|\s*\[下载\]\(([^)]+)\)/g
    text = text.replace(embeddedDocPattern, (match, fileName, fileType, previewUrl1, previewUrl2, downloadUrl) => {
      const previewUrl = previewUrl2 || previewUrl1
      let oleId = previewUrl.split('/ole/')[1] || ''
      oleId = oleId.split('?')[0].split('#')[0].split('/')[0]
      if (!oleId) return match
      
      const modalId = `ole-viewer-${uploadId}-${oleId.replace(/[^a-zA-Z0-9]/g, '-')}`
      
      return `<div style="margin: 15px 0; padding: 10px; background-color: #f9f9f9; border-left: 3px solid #1890ff;">
    <strong>${fileName}</strong> (${fileType})
    <br>
    <a href="javascript:void(0)" onclick="window.openOleViewer('${previewUrl}', '${downloadUrl}', '${modalId}')" style="color: #1890ff; cursor: pointer; text-decoration: underline; margin-right: 15px;">查看</a>
    <a href="javascript:void(0)" onclick="window.downloadOleFile('${downloadUrl}')" style="color: #1890ff; cursor: pointer; text-decoration: underline;">下载</a>
</div>`
    })
    
    // 处理其他嵌入文档链接
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
  text = text.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, alt, url) => {
    if (url.includes('/images/') || url.startsWith('/api/document-upload/')) {
      const linkText = alt || url.split('/images/')[1] || url.split('/').pop() || '图片'
      return `[${linkText}](${url})`
    }
    return match
  })
  
  return text
    .replace(/^### (.*$)/gim, '<h3>$1</h3>')
    .replace(/^## (.*$)/gim, '<h2>$1</h2>')
    .replace(/^# (.*$)/gim, '<h1>$1</h1>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, linkText, url) => {
      if (url.includes('/images/') || (url.startsWith('/api/document-upload/') && url.includes('images/'))) {
        return `<a href="${url}" target="_blank" style="color: #1890ff; cursor: pointer; text-decoration: underline;">${linkText}</a>`
      }
      if (url.includes('/ole/')) {
        return match
      }
      return `<a href="${url}" target="_blank">${linkText}</a>`
    })
    .replace(/\n\n/g, '<br><br>')
    .replace(/\n/g, '<br>')
}

// 加载历史对话记录
const loadChatHistory = async () => {
  if (!selectedKB.value?.id) {
    return
  }
  
  try {
    const response = await getChatHistory(selectedKB.value.id, 1, 50)
    console.log('加载历史对话响应:', response)
    if (response && response.items && response.items.length > 0) {
      // 将历史对话转换为前端消息格式
      const historyMessages = []
      for (const history of response.items) {
        console.log('处理历史记录:', history.id, 'retrieval_results:', history.retrieval_results, '类型:', typeof history.retrieval_results, '是否为数组:', Array.isArray(history.retrieval_results))
        // 用户消息
        historyMessages.push({
          role: 'user',
          content: history.user_message,
          timestamp: new Date(history.created_at).getTime()
        })
        // 助手回复（包含检索结果）
        // 确保 retrieval_results 是数组格式
        let retrievalResults = []
        if (history.retrieval_results) {
          // 如果已经是数组，直接使用
          if (Array.isArray(history.retrieval_results)) {
            retrievalResults = history.retrieval_results
          } else if (typeof history.retrieval_results === 'string') {
            // 如果是JSON字符串，解析它
            try {
              retrievalResults = JSON.parse(history.retrieval_results)
            } catch (e) {
              console.error('解析 retrieval_results JSON 失败:', e)
              retrievalResults = []
            }
          } else {
            // 如果是对象，尝试转换为数组
            retrievalResults = [history.retrieval_results]
          }
        }
        console.log('处理后的 retrieval_results:', retrievalResults, '长度:', retrievalResults.length, '是否为数组:', Array.isArray(retrievalResults))
        if (retrievalResults.length > 0) {
          console.log('第一个检索结果示例:', retrievalResults[0])
          console.log('第一个检索结果的type字段:', retrievalResults[0].type, 'source_type字段:', retrievalResults[0].source_type)
          // 测试分类函数
          console.log('getCommunities结果:', getCommunities(retrievalResults).length)
          console.log('getEpisodes结果:', getEpisodes(retrievalResults).length)
          console.log('getRelationships结果:', getRelationships(retrievalResults).length)
          console.log('getEntities结果:', getEntities(retrievalResults).length)
        }
        
        const assistantMsg = {
          role: 'assistant',
          content: history.assistant_message,
          retrieval_results: retrievalResults,  // 恢复检索结果
          retrieval_count: history.retrieval_summary?.count || retrievalResults.length || 0,
          retrieval_time: history.retrieval_summary?.time_ms || 0,
          has_context: (history.retrieval_summary?.count || retrievalResults.length || 0) > 0,
          timestamp: new Date(history.created_at).getTime()
        }
        console.log('创建的助手消息对象:', assistantMsg, 'retrieval_results长度:', assistantMsg.retrieval_results?.length, 'retrieval_count:', assistantMsg.retrieval_count)
        historyMessages.push(assistantMsg)
      }
      // 将历史消息添加到当前消息列表（如果当前列表为空）
      if (chatMessages.value.length === 0) {
        chatMessages.value = historyMessages
        console.log('历史消息已加载到 chatMessages，总数:', chatMessages.value.length)
        // 检查每条消息的检索结果
        chatMessages.value.forEach((msg, idx) => {
          if (msg.role === 'assistant') {
            console.log(`消息 ${idx}: retrieval_results长度=${msg.retrieval_results?.length || 0}, retrieval_count=${msg.retrieval_count || 0}`)
          }
        })
        // 滚动到底部
        nextTick(() => {
          scrollToBottom()
        })
      }
    }
  } catch (error) {
    console.error('加载历史对话失败:', error)
    // 不显示错误提示，因为历史对话是可选的
  }
}

onMounted(() => {
  loadKnowledgeBases()
  
  // 从本地存储加载检索设置
  const saved = localStorage.getItem('retrievalSettings')
  if (saved) {
    try {
      const parsed = JSON.parse(saved)
      retrievalSettings.value = { ...retrievalSettings.value, ...parsed }
    } catch (e) {
      console.error('加载保存的检索设置失败:', e)
    }
  }
})

// 监听文档库弹窗打开，加载文档列表
watch(showDocumentLibraryModal, (visible) => {
  if (visible) {
    loadLibraryDocuments()
  }
})

// 监听知识库选择变化，加载历史对话
watch(selectedKB, (newKb) => {
  if (newKb && newKb.id) {
    // 清空当前消息
    chatMessages.value = []
    // 加载历史对话
    loadChatHistory()
  }
}, { immediate: false })
</script>

<style scoped>
.kb-category-section {
  margin-bottom: 16px;
}

.category-header {
  display: flex;
  align-items: center;
  padding: 8px 0;
  color: #262626;
  gap: 4px;
  position: relative;
}

.category-header .add-kb-btn {
  position: absolute;
  right: 0;
  padding: 0 !important;
  height: auto !important;
}

.kb-list {
  margin-top: 4px;
}

.kb-item {
  display: flex !important;
  align-items: center !important;
  gap: 2px !important;
  padding: 6px 12px;
  margin: 2px 0;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.3s;
}

.kb-item:hover {
  background: #f5f5f5;
}

.kb-item.active {
  background: #e6f7ff;
  color: #1890ff;
}

/* 图标样式优化 - 确保所有图标都应用 */
.kb-item .anticon,
.kb-item svg,
.kb-item-icon {
  font-size: 16px !important;
  flex-shrink: 0 !important;
  margin-right: 0 !important;
  width: 16px !important;
  height: 16px !important;
  display: inline-block !important;
}

.kb-item span {
  margin-left: 0 !important;
  padding-left: 0 !important;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kb-detail-container {
  max-width: 1200px;
  margin: 0 auto;
}

.kb-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding-bottom: 16px;
  border-bottom: 1px solid #e8e8e8;
}

.kb-title-section {
  display: flex;
  align-items: center;
  flex: 1;
}

.kb-actions {
  display: flex;
  gap: 8px;
}

.chat-container {
  display: flex;
  flex-direction: column;
  height: 400px;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  background: #fafafa;
  border-radius: 4px;
  margin-bottom: 16px;
}

.chat-message {
  margin-bottom: 16px;
}

.chat-message.user {
  text-align: right;
}

.chat-message.user .message-content {
  display: inline-block;
  background: #1890ff;
  color: white;
  padding: 8px 12px;
  border-radius: 4px;
  max-width: 70%;
}

.chat-message.assistant .message-content {
  display: inline-block;
  background: white;
  padding: 8px 12px;
  border-radius: 4px;
  max-width: 70%;
}

.chat-input {
  display: flex;
  gap: 8px;
}

.document-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.document-item {
  display: flex;
  align-items: center;
  padding: 12px;
  border: 1px solid #e8e8e8;
  border-radius: 4px;
  transition: all 0.3s;
}

.document-item:hover {
  background: #f5f5f5;
  border-color: #1890ff;
}

.document-info {
  flex: 1;
  min-width: 0;
}

.document-name {
  font-size: 14px;
  color: #262626;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-bottom: 4px;
}

.document-meta {
  font-size: 12px;
  color: #8c8c8c;
}

/* 右侧问答面板样式 */
.qa-panel {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 64px);
}

.qa-panel-content {
  flex: 1;
  overflow-y: auto;
  padding: 0;
}

.qa-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #8c8c8c;
}

.empty-icon {
  margin-bottom: 16px;
}

.empty-text {
  font-size: 14px;
  color: #8c8c8c;
}

.qa-panel-footer {
  padding: 16px;
  border-top: 1px solid #e8e8e8;
  background: #fafafa;
}

.content-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.chat-input-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.chat-controls-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.chat-controls-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ai-disclaimer {
  font-size: 12px;
  color: #8c8c8c;
  text-align: center;
  margin-top: 8px;
}

/* 三列布局样式 */
.kb-layout {
  display: flex !important;
}

.kb-sider-left {
  background: #fff !important;
  border-right: 1px solid #e8e8e8 !important;
  position: relative !important;
  flex: 0 0 240px !important;
  min-width: 200px !important;
  max-width: 400px !important;
}

.kb-content-middle {
  padding: 24px !important;
  background: #f0f2f5 !important;
  flex: 1 !important;
  position: relative !important;
  min-width: 400px !important;
}

.kb-sider-right {
  background: #fff !important;
  border-left: 1px solid #e8e8e8 !important;
  position: relative !important;
  flex: 2 !important;
  min-width: 500px !important;
}

/* 当右侧有固定宽度时，取消flex */
.kb-sider-right[style*="width"] {
  flex: none !important;
}

/* 拖拽条样式 */
.resize-handle {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 4px;
  cursor: col-resize;
  z-index: 10;
  background: transparent;
  transition: background 0.2s;
}

.resize-handle:hover {
  background: #1890ff;
}

.resize-handle-right {
  right: -2px;
}

.resize-handle-left {
  left: -2px;
}

/* 添加知识库按钮样式 */

.add-kb-btn {
  margin-left: auto;
  opacity: 0.6;
  transition: opacity 0.3s;
}

.add-kb-btn:hover {
  opacity: 1;
}

.add-kb-btn-inline {
  margin-left: auto;
  opacity: 0.6;
  transition: opacity 0.3s;
  padding: 0 !important;
  height: auto !important;
}

.add-kb-btn-inline:hover {
  opacity: 1;
}

/* 确保collapse header中的"+"按钮与category-header中的对齐 */
:deep(.ant-collapse-header) {
  padding: 8px 0 !important;
}

:deep(.ant-collapse-header .add-kb-btn-inline) {
  margin-left: auto;
  margin-right: 0;
}
</style>

