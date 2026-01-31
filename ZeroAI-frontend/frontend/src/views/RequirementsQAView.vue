<template>
  <a-card>
    <template #title>
      <span>智能问答</span>
    </template>
    
    <a-tabs v-model:activeKey="activeTab">
      <!-- 需求文档问答 -->
      <a-tab-pane key="qa" tab="需求文档问答">
        <!-- Tab 1 - 检索模式和文档选择（独立组件1） -->
    <a-form :label-col="{ span: 4 }" :wrapper-col="{ span: 20 }" style="margin-bottom: 24px">
          <a-form-item label="检索模式">
            <a-radio-group v-model:value="documentMode_qa" @change="handleModeChange_qa">
              <a-radio value="single">单文档</a-radio>
              <a-radio value="multiple">多文档</a-radio>
              <a-radio value="all">全部文档</a-radio>
            </a-radio-group>
          </a-form-item>
          
          <!-- 单文档模式 -->
          <a-form-item v-if="documentMode_qa === 'single'" label="选择文档">
        <a-select
              v-model:value="selectedGroupId_qa"
          placeholder="请选择要问答的文档"
          style="width: 100%"
          :loading="loadingDocuments"
              :disabled="loadingDocuments"
              @change="handleDocumentChange_qa"
              allow-clear
        >
          <a-select-option
            v-for="doc in documents"
            :key="doc.document_id"
            :value="doc.document_id"
                :disabled="false"
          >
                {{ doc.file_name || doc.document_name }} ({{ doc.document_id }})
          </a-select-option>
        </a-select>
            <div v-if="documents.length === 0 && !loadingDocuments" style="color: #ff4d4f; font-size: 12px; margin-top: 4px">
              没有可用的文档，请先在"文档管理"中上传并处理文档
            </div>
          </a-form-item>
          
          <!-- 多文档模式 -->
          <a-form-item v-if="documentMode_qa === 'multiple'" label="选择文档">
            <a-select
              v-model:value="selectedGroupIds_qa"
              mode="multiple"
              placeholder="请选择要问答的文档（至少2个）"
              style="width: 100%"
              :loading="loadingDocuments"
              :disabled="loadingDocuments"
              @change="handleDocumentChange_qa"
              allow-clear
        >
          <a-select-option
            v-for="doc in documents"
            :key="doc.document_id"
            :value="doc.document_id"
                :disabled="false"
          >
                {{ doc.file_name || doc.document_name }} ({{ doc.document_id }})
          </a-select-option>
        </a-select>
            <div v-if="documents.length === 0 && !loadingDocuments" style="color: #ff4d4f; font-size: 12px; margin-top: 4px">
              没有可用的文档，请先在"文档管理"中上传并处理文档
            </div>
          </a-form-item>
          
          <!-- 全部文档模式 -->
          <a-form-item v-if="documentMode_qa === 'all'" label="检索范围">
            <a-alert
              message="将检索所有已处理的文档"
              type="info"
              show-icon
              style="margin-bottom: 8px"
            />
            <div style="color: #999; font-size: 12px">
              当前共有 {{ documents.length }} 个文档
            </div>
      </a-form-item>
    </a-form>

        <!-- Tab 1 - 选择LLM（独立组件1） -->
        <a-form :label-col="{ span: 4 }" :wrapper-col="{ span: 20 }">
          <a-form-item label="选择LLM">
            <a-space>
              <a-radio-group v-model:value="selectedProvider_qa">
                <a-radio value="local">本地大模型</a-radio>
              </a-radio-group>
              <a-slider
                v-model:value="temperature_qa"
                :min="0"
                :max="2"
                :step="0.1"
                style="width: 200px; margin-left: 24px"
                :tooltip-formatter="(val) => `温度: ${val}`"
              />
              <span style="color: #999; font-size: 12px">温度: {{ temperature_qa }}</span>
              <a-switch
                v-model:checked="useThinking_qa"
                style="margin-left: 24px"
                :disabled="selectedProvider_qa !== 'local'"
              >
                <template #checkedChildren>Thinking</template>
                <template #unCheckedChildren>Thinking</template>
              </a-switch>
              <span v-if="selectedProvider_qa === 'local'" style="color: #999; font-size: 12px">启用Thinking模式</span>
              <span v-else style="color: #ccc; font-size: 12px">（仅本地大模型支持）</span>
            </a-space>
          </a-form-item>
          
          <a-form-item label="检索设置">
            <a-space>
              <a-tag :color="getSchemeColor(crossEncoderMode_qa)">
                {{ getSchemeLabel(crossEncoderMode_qa) }}
              </a-tag>
              <a-button type="link" size="small" @click="showRetrievalSettings = true">
                <template #icon><SettingOutlined /></template>
                设置
              </a-button>
            </a-space>
          </a-form-item>
        </a-form>

        <!-- 对话区域 -->
        <div
          style="
            border: 1px solid #d9d9d9;
            border-radius: 8px;
            padding: 16px;
            min-height: 400px;
            max-height: 600px;
            overflow-y: auto;
            background: #fafafa;
            margin-bottom: 16px;
          "
          ref="chatContainer"
        >
          <!-- 空状态 -->
          <a-empty
            v-if="messages.length === 0"
            description="请先选择文档，然后开始提问。系统会自动从该文档的知识图谱检索相关信息来回答您的问题。"
            style="margin: 60px 0"
          />

          <!-- 消息列表 -->
          <div v-for="(msg, index) in messages" :key="index" style="margin-bottom: 24px">
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
                  v-if="msg.retrieval_results && msg.retrieval_results.length > 0"
                  :bordered="false"
                  style="background: white; border: 1px solid #e8e8e8; border-radius: 8px"
                >
                  <template #expandIcon="{ isActive }">
                    <CaretRightOutlined :rotate="isActive ? 90 : 0" />
                  </template>
                  <a-collapse-panel
                    :key="index"
                    :header="`检索结果 (${msg.retrieval_count} 个，耗时 ${msg.retrieval_time?.toFixed(0) || 0}ms)`"
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
                                    <div v-if="item.properties?.member_names && item.properties.member_names.length > 0">
                                      <strong>成员：</strong>
                                      {{ item.properties.member_names.slice(0, 5).join(', ') }}
                                      <span v-if="item.properties.member_names.length > 5">
                                        等{{ item.properties.member_names.length }}个
                                    </span>
                                    </div>
                                  </div>
                                </template>
                              </a-list-item-meta>
                            </a-list-item>
                          </template>
                        </a-list>
                      </div>

                      <!-- Episode列表（完整上下文） -->
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
                                    <div v-if="item.properties?.source_description" style="margin-top: 4px">
                                      <strong>来源：</strong>{{ item.properties.source_description }}
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
                                    <span v-for="(value, key) in item.properties" :key="key" style="margin-right: 12px">
                                      <span v-if="key !== 'id'">{{ key }}: {{ formatValue(value) }}</span>
                                    </span>
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
                                <template #description>
                                  <div style="font-size: 12px; color: #999">
                                    <span v-for="(value, key) in item.properties" :key="key" style="margin-right: 12px">
                                      <span v-if="key !== 'id' && key !== 'name' && key !== 'name_embedding'">
                                        {{ key }}: {{ formatValue(value) }}
                                      </span>
                                    </span>
                                  </div>
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
          <div v-if="chatting" style="text-align: center; padding: 20px">
            <a-spin size="large">
              <template #indicator>
                <LoadingOutlined style="font-size: 24px" spin />
              </template>
            </a-spin>
            <div style="margin-top: 12px; color: #999">
              {{ retrievalStatus }}
            </div>
          </div>
        </div>

        <!-- 输入区域 -->
        <a-form :label-col="{ span: 0 }" :wrapper-col="{ span: 24 }">
          <a-form-item>
            <a-textarea
              v-model:value="inputMessage"
              :rows="3"
              :placeholder="getInputPlaceholder()"
              @pressEnter="handleSendMessage"
              :disabled="chatting || !canSendMessage"
            />
          </a-form-item>
          <a-form-item>
            <a-space>
              <a-button 
                type="primary" 
                @click="handleSendMessage" 
                :loading="chatting" 
                :disabled="!inputMessage.trim() || !canSendMessage"
              >
                <template #icon><SendOutlined /></template>
                发送
              </a-button>
              <a-button @click="handleClear">清空对话</a-button>
              <a-button @click="handleClearAll" danger>清除所有</a-button>
            </a-space>
          </a-form-item>
        </a-form>
      </a-tab-pane>

      <!-- 需求文档生成 -->
      <a-tab-pane key="similar" tab="需求文档生成">
        <!-- Tab 2 - 检索模式和文档选择（独立组件2） -->
        <a-form :label-col="{ span: 4 }" :wrapper-col="{ span: 20 }" style="margin-bottom: 24px">
          <a-form-item label="检索模式">
            <a-radio-group v-model:value="documentMode_similar" @change="handleModeChange_similar">
              <a-radio value="single">单文档</a-radio>
              <a-radio value="multiple">多文档</a-radio>
              <a-radio value="all">全部文档</a-radio>
            </a-radio-group>
          </a-form-item>
          
          <!-- 单文档模式 -->
          <a-form-item v-if="documentMode_similar === 'single'" label="选择文档">
            <a-select
              v-model:value="selectedGroupId_similar"
              placeholder="请选择要问答的文档"
              style="width: 100%"
              :loading="loadingDocuments"
              :disabled="loadingDocuments"
              @change="handleDocumentChange_similar"
              allow-clear
            >
              <a-select-option
                v-for="doc in documents"
                :key="doc.document_id"
                :value="doc.document_id"
                :disabled="false"
              >
                {{ doc.file_name || doc.document_name }} ({{ doc.document_id }})
              </a-select-option>
            </a-select>
            <div v-if="documents.length === 0 && !loadingDocuments" style="color: #ff4d4f; font-size: 12px; margin-top: 4px">
              没有可用的文档，请先在"文档管理"中上传并处理文档
            </div>
          </a-form-item>
          
          <!-- 多文档模式 -->
          <a-form-item v-if="documentMode_similar === 'multiple'" label="选择文档">
            <a-select
              v-model:value="selectedGroupIds_similar"
              mode="multiple"
              placeholder="请选择要问答的文档（至少2个）"
              style="width: 100%"
              :loading="loadingDocuments"
              :disabled="loadingDocuments"
              @change="handleDocumentChange_similar"
              allow-clear
            >
              <a-select-option
                v-for="doc in documents"
                :key="doc.document_id"
                :value="doc.document_id"
                :disabled="false"
              >
                {{ doc.file_name || doc.document_name }} ({{ doc.document_id }})
              </a-select-option>
            </a-select>
            <div v-if="documents.length === 0 && !loadingDocuments" style="color: #ff4d4f; font-size: 12px; margin-top: 4px">
              没有可用的文档，请先在"文档管理"中上传并处理文档
            </div>
          </a-form-item>
          
          <!-- 全部文档模式 -->
          <a-form-item v-if="documentMode_similar === 'all'" label="检索范围">
            <a-alert
              message="将检索所有已处理的文档"
              type="info"
              show-icon
              style="margin-bottom: 8px"
            />
            <div style="color: #999; font-size: 12px">
              当前共有 {{ documents.length }} 个文档
            </div>
          </a-form-item>
        </a-form>

        <!-- Tab 2 - 选择LLM和配置参数（独立组件2） -->
        <a-form :label-col="{ span: 4 }" :wrapper-col="{ span: 20 }" style="margin-bottom: 24px">
          <a-form-item label="选择LLM">
            <a-radio-group v-model:value="selectedProvider_similar">
              <a-radio value="local">本地大模型</a-radio>
            </a-radio-group>
          </a-form-item>
          
          <a-form-item label="生成配置">
            <a-space>
              <span>最大迭代次数:</span>
              <a-input-number v-model:value="maxIterations" :min="1" :max="10" style="width: 100px" />
              <span style="margin-left: 16px">质量阈值:</span>
              <a-slider v-model:value="qualityThreshold" :min="0" :max="100" style="width: 150px" />
              <span style="margin-left: 8px">{{ qualityThreshold }}</span>
              <span style="margin-left: 16px">检索数量:</span>
              <a-input-number v-model:value="retrievalLimit" :min="5" :max="50" style="width: 100px" />
              <a-switch
                v-model:checked="useThinking_generate"
                style="margin-left: 24px"
                :disabled="selectedProvider_similar !== 'local'"
              >
                <template #checkedChildren>Thinking</template>
                <template #unCheckedChildren>Thinking</template>
              </a-switch>
              <span v-if="selectedProvider_similar === 'local'" style="color: #999; font-size: 12px">启用Thinking模式</span>
              <span v-else style="color: #ccc; font-size: 12px">（仅本地大模型支持）</span>
            </a-space>
          </a-form-item>
        </a-form>

        <a-form :label-col="{ span: 4 }" :wrapper-col="{ span: 20 }">
          <a-form-item label="问题描述">
            <a-textarea
              v-model:value="similarQuery"
              :rows="4"
              placeholder="描述你的需求或问题，系统会根据检索到的相关内容生成需求文档..."
            />
          </a-form-item>
          <a-form-item>
            <a-space>
              <a-button 
                type="primary" 
                @click="handleGenerateDocument" 
                :loading="loadingSimilar"
                :disabled="!similarQuery.trim()"
              >
                生成需求文档
              </a-button>
              <span style="color: #999; font-size: 12px">
                最大迭代次数: {{ maxIterations }} | 质量阈值: {{ qualityThreshold }} | 检索数量: {{ retrievalLimit }}
              </span>
            </a-space>
          </a-form-item>
        </a-form>

        <!-- 生成任务状态 -->
        <a-alert
          v-if="generationTaskId"
          :message="`任务已提交，任务ID: ${generationTaskId}`"
          type="info"
          show-icon
          style="margin-top: 24px"
        >
          <template #description>
            <a-space>
              <span>请前往"任务管理"页面查看生成进度</span>
              <a-button type="link" size="small" @click="goToTaskManagement">查看任务</a-button>
            </a-space>
          </template>
        </a-alert>

        <a-empty
          v-else-if="!loadingSimilar"
          description='输入问题描述后，点击"生成需求文档"按钮'
          style="margin: 60px 0"
        />
      </a-tab-pane>

      <!-- 需求分析 Tab页已删除 -->
    </a-tabs>

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
            <a-descriptions-item label="完整内容" :span="2" v-if="selectedRetrievalItem.properties?.content">
              <div 
                v-html="formatMarkdown(selectedRetrievalItem.properties.content)"
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
            <a-descriptions-item label="UUID" v-if="selectedRetrievalItem.uuid">
              {{ selectedRetrievalItem.uuid }}
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
            <a-descriptions-item label="UUID" v-if="selectedRetrievalItem.uuid">
              {{ selectedRetrievalItem.uuid }}
            </a-descriptions-item>
          </template>

          <!-- 其他属性 -->
          <a-descriptions-item label="完整属性" :span="2" v-if="selectedRetrievalItem.properties">
            <pre style="background: #f5f5f5; padding: 12px; border-radius: 4px; overflow-x: auto; max-height: 300px; overflow-y: auto; font-size: 12px;">{{ formatProperties(selectedRetrievalItem.properties) }}</pre>
          </a-descriptions-item>
        </a-descriptions>
      </div>
    </a-modal>
    
    <!-- 检索设置弹窗 -->
    <RetrievalSettingsModal
      v-model:open="showRetrievalSettings"
      :settings="retrievalSettings"
      :support-thinking="selectedProvider_qa === 'local'"
      @confirm="handleRetrievalSettingsConfirm"
    />
  </a-card>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { storeToRefs } from 'pinia'
import { message } from 'ant-design-vue'
import { useRouter } from 'vue-router'
import { useRequirementsQAStore } from '../stores/requirementsQA'
import {
  SendOutlined,
  LoadingOutlined,
  CaretRightOutlined,
  ArrowRightOutlined,
  EyeOutlined,
  QuestionCircleOutlined,
  SettingOutlined
} from '@ant-design/icons-vue'
import { qaChat, qaSimilarRequirements, qaAnalyzeRequirement, generateRequirementDocumentAsync } from '../api/requirements'
import { getDocumentUploadList } from '../api/documentUpload'
import RetrievalSettingsModal from '../components/RetrievalSettingsModal.vue'

const router = useRouter()
const store = useRequirementsQAStore()

const activeTab = ref('qa')
const documents = ref([])
const loadingDocuments = ref(false)
const chatContainer = ref(null)

// 临时状态（不需要持久化）
const chatting = ref(false)
const loadingSimilar = ref(false)
const analyzing = ref(false)
const generationTaskId = ref(null)

// 生成文档配置参数
const maxIterations = ref(3)
const qualityThreshold = ref(80)
const retrievalLimit = ref(20)
const useThinking_generate = ref(false)

// 检索设置弹窗
const showRetrievalSettings = ref(false)
const retrievalSettings = ref({
  scheme: 'default',
  limit: 20,
  simThreshold: 60,
  useThinking: false,
  truncateLength: 500,
  summaryLength: 200,
  fastThreshold: 50
})

// 从store获取状态（使用storeToRefs确保响应式）
const {
  // Tab 1
  documentMode_qa,
  selectedGroupId_qa,
  selectedGroupIds_qa,
  selectedProvider_qa,
  temperature_qa,
  useThinking_qa,
  crossEncoderMode_qa,
  messages,
  inputMessage,
  retrievalStatus,
  // Tab 2
  documentMode_similar,
  selectedGroupId_similar,
  selectedGroupIds_similar,
  selectedProvider_similar,
  similarQuery,
  similarDocuments,
  // Tab 3
  documentMode_analyze,
  selectedGroupId_analyze,
  selectedGroupIds_analyze,
  selectedProvider_analyze,
  analysisResult
} = storeToRefs(store)

const formatTime = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

const formatDateTime = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  return date.toLocaleString('zh-CN')
}

const formatValue = (value) => {
  if (typeof value === 'object') {
    return JSON.stringify(value)
  }
  return String(value)
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

const getCommunities = (results) => {
  if (!results) return []
  return results.filter((r) => r.type === 'community')
}

const getEpisodes = (results) => {
  if (!results) return []
  return results.filter((r) => r.type === 'episode')
}

const getRelationships = (results) => {
  if (!results) return []
  return results.filter((r) => r.type === 'edge')
}

const getEntities = (results) => {
  if (!results) return []
  // 同时支持 'node' 和 'entity' 类型（兼容旧格式和新格式）
  return results.filter((r) => r.type === 'node' || r.type === 'entity')
}

const copyMessage = (content) => {
  navigator.clipboard.writeText(content).then(() => {
    message.success('已复制到剪贴板')
  })
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

// 格式化属性为JSON字符串
const formatProperties = (properties) => {
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

// 格式化Markdown内容为HTML，支持图片和表格
const formatMarkdown = (text) => {
  if (!text) return ''
  
  // 转义HTML特殊字符（除了我们需要的标签）
  const escapeHtml = (str) => {
    const div = document.createElement('div')
    div.textContent = str
    return div.innerHTML
  }
  
  // 1. 处理Markdown表格（在转换为HTML之前）
  // 匹配Markdown表格格式：| 列1 | 列2 | ... |
  // 支持有分隔行和没有分隔行的表格
  const tableRegex = /(\|.+\|(?:\s*\n\s*\|[:\-\s\|]+\|)?(?:\s*\n\s*\|.+\|)+)/g
  let processedText = text.replace(tableRegex, (match) => {
    const lines = match.trim().split('\n').filter(line => line.trim())
    if (lines.length < 2) return match // 至少需要表头和一行数据
    
    // 解析表头
    const headerLine = lines[0].trim()
    const headers = headerLine.split('|').map(h => h.trim()).filter(h => h)
    
    // 跳过分隔行（|---|---|）
    let dataStartIndex = 1
    if (lines[1].trim().match(/^[\|\s\-\:]+$/)) {
      dataStartIndex = 2
    }
    
    // 解析数据行
    const rows = []
    for (let i = dataStartIndex; i < lines.length; i++) {
      const cells = lines[i].split('|').map(c => c.trim()).filter((c, idx) => idx > 0 && idx < lines[i].split('|').length - 1)
      if (cells.length > 0) {
        rows.push(cells)
      }
    }
    
    // 构建HTML表格
    let htmlTable = '<table style="border-collapse: collapse; width: 100%; margin: 16px 0; border: 1px solid #d9d9d9;">'
    
    // 表头
    htmlTable += '<thead><tr style="background: #fafafa;">'
    headers.forEach(header => {
      htmlTable += `<th style="border: 1px solid #d9d9d9; padding: 8px 12px; text-align: left; font-weight: 600;">${escapeHtml(header)}</th>`
    })
    htmlTable += '</tr></thead>'
    
    // 表体
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
  
  // 2. 处理Markdown图片：![alt](url)
  processedText = processedText.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, alt, url) => {
    // 如果URL是图片API路径，显示为可点击的图片链接
    if (url.includes('/images/') || url.startsWith('/api/document-upload/') || url.startsWith('/api/word-document/')) {
      const linkText = alt || '图片'
      return `<a href="${url}" target="_blank" style="color: #1890ff; cursor: pointer; text-decoration: underline; display: inline-block; margin: 8px 0;">
        <img src="${url}" alt="${escapeHtml(linkText)}" style="max-width: 100%; height: auto; border: 1px solid #d9d9d9; border-radius: 4px; padding: 4px; background: #fafafa;" 
        onerror="this.style.display='none'; this.nextElementSibling.style.display='inline';">
        <span style="display: none;">${escapeHtml(linkText)}</span>
      </a>`
    }
    // 普通图片链接
    return `<img src="${url}" alt="${escapeHtml(alt || '')}" style="max-width: 100%; height: auto; margin: 8px 0;">`
  })
  
  // 3. 处理Markdown链接：[text](url)
  processedText = processedText.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, linkText, url) => {
    // 跳过已经处理过的图片链接
    if (match.includes('<img')) return match
    return `<a href="${url}" target="_blank" style="color: #1890ff; text-decoration: underline;">${escapeHtml(linkText)}</a>`
  })
  
  // 4. 处理标题
  processedText = processedText.replace(/^#### (.*$)/gim, '<h4 style="margin: 16px 0 8px 0; font-size: 16px; font-weight: 600;">$1</h4>')
  processedText = processedText.replace(/^### (.*$)/gim, '<h3 style="margin: 20px 0 12px 0; font-size: 18px; font-weight: 600;">$1</h3>')
  processedText = processedText.replace(/^## (.*$)/gim, '<h2 style="margin: 24px 0 16px 0; font-size: 20px; font-weight: 600;">$1</h2>')
  processedText = processedText.replace(/^# (.*$)/gim, '<h1 style="margin: 28px 0 20px 0; font-size: 24px; font-weight: 600;">$1</h1>')
  
  // 5. 处理粗体 **text**
  processedText = processedText.replace(/\*\*([^\*]+)\*\*/g, '<strong>$1</strong>')
  
  // 6. 处理斜体 *text*
  processedText = processedText.replace(/\*([^\*]+)\*/g, '<em>$1</em>')
  
  // 7. 处理代码块 ```code```
  processedText = processedText.replace(/```([^`]+)```/g, '<pre style="background: #f5f5f5; padding: 12px; border-radius: 4px; overflow-x: auto; margin: 12px 0;"><code>$1</code></pre>')
  
  // 8. 处理行内代码 `code`
  processedText = processedText.replace(/`([^`]+)`/g, '<code style="background: #f5f5f5; padding: 2px 6px; border-radius: 3px; font-family: monospace;">$1</code>')
  
  // 9. 处理列表项（无序列表）
  processedText = processedText.replace(/^[\-\*\+] (.+)$/gim, '<li style="margin: 4px 0;">$1</li>')
  // 包装连续的<li>为<ul>
  processedText = processedText.replace(/(<li[^>]*>.*?<\/li>(?:\s*<li[^>]*>.*?<\/li>)*)/gs, '<ul style="margin: 8px 0; padding-left: 24px;">$1</ul>')
  
  // 10. 处理换行
  processedText = processedText.replace(/\n\n/g, '<br><br>')
  processedText = processedText.replace(/\n/g, '<br>')
  
  return processedText
}

const loadDocuments = async () => {
  loadingDocuments.value = true
  try {
    // 使用新的 document_upload API
    const response = await getDocumentUploadList(1, 100, null, 'completed')
    console.log('文档列表响应:', response)
    if (response && response.documents) {
      // 只显示已完成处理的文档（有 document_id）
      documents.value = response.documents.filter(doc => doc.document_id && doc.status === 'completed')
      console.log('过滤后的文档列表:', documents.value)
      // 去重：只保留每个 document_id 的一个版本（选择最新的）
      const groupIdMap = new Map()
      documents.value.forEach(doc => {
        const groupId = doc.document_id
        if (!groupIdMap.has(groupId) || 
            (doc.id || 0) > (groupIdMap.get(groupId).id || 0)) {
          groupIdMap.set(groupId, doc)
        }
      })
      documents.value = Array.from(groupIdMap.values())
      console.log('去重后的文档列表:', documents.value)
      if (documents.value.length === 0) {
        message.warning('没有可用的文档，请先在"文档管理"中上传并处理文档')
      }
    } else {
      console.warn('文档列表为空或格式不正确:', response)
      documents.value = []
      message.warning('没有可用的文档，请先在"文档管理"中上传并处理文档')
    }
  } catch (error) {
    console.error('加载文档列表失败:', error)
    message.error(`加载文档列表失败: ${error.message || '未知错误'}`)
    documents.value = []
  } finally {
    loadingDocuments.value = false
  }
}

// Tab 1 - 处理函数
const handleModeChange_qa = () => {
  // 切换模式时清空选择和对话
  selectedGroupId_qa.value = null
  selectedGroupIds_qa.value = []
  messages.value = []
}

const handleDocumentChange_qa = () => {
  // 切换文档时清空对话
  messages.value = []
}

// Tab 2 - 处理函数
const handleModeChange_similar = () => {
  // 切换模式时清空选择
  selectedGroupId_similar.value = null
  selectedGroupIds_similar.value = []
  similarDocuments.value = []
}

const handleDocumentChange_similar = () => {
  // 切换文档时清空结果
  similarDocuments.value = []
}

// Tab 3 - 处理函数
const handleModeChange_analyze = () => {
  // 切换模式时清空选择
  selectedGroupId_analyze.value = null
  selectedGroupIds_analyze.value = []
  analysisResult.value = null
}

const handleDocumentChange_analyze = () => {
  // 切换文档时清空结果
  analysisResult.value = null
}

const handleSendMessage = async () => {
  if (!inputMessage.value.trim()) {
    message.warning('请输入问题')
    return
  }
  
  // 检查文档选择（使用Tab 1的状态）
  if (!canSendMessage.value) {
    if (documentMode_qa.value === 'single') {
      message.warning('请先选择文档')
    } else if (documentMode_qa.value === 'multiple') {
      message.warning('多文档模式需要至少选择2个文档')
    } else {
      message.warning('没有可用的文档')
    }
    return
  }

  const userMessage = inputMessage.value.trim()
  inputMessage.value = ''

  // 添加用户消息
  messages.value.push({
    role: 'user',
    content: userMessage,
    timestamp: Date.now()
  })

  chatting.value = true
  retrievalStatus.value = '正在检索知识图谱...'

  try {
    // 构建消息列表
    const messageList = messages.value.map(msg => ({
      role: msg.role,
      content: msg.content
    }))

    // 根据模式调用API（使用Tab 1的状态）
    const response = await qaChat(
      documentMode_qa.value === 'single' ? selectedGroupId_qa.value : null,
      documentMode_qa.value === 'multiple' ? selectedGroupIds_qa.value : null,
      documentMode_qa.value === 'all',
      messageList,
      selectedProvider_qa.value,
      temperature_qa.value,
      useThinking_qa.value,
      crossEncoderMode_qa.value
    )

    // 添加AI回复
    messages.value.push({
      role: 'assistant',
      content: response.content,
      retrieval_results: response.retrieval_results,
      retrieval_count: response.retrieval_count,
      retrieval_time: response.retrieval_time,
      has_context: response.has_context,
      timestamp: Date.now()
    })

    // 滚动到底部
    await nextTick()
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  } catch (error) {
    console.error('发送消息失败:', error)
    message.error(`发送消息失败: ${error.message || '未知错误'}`)
  } finally {
    chatting.value = false
    retrievalStatus.value = '正在检索知识图谱...'
  }
}

const handleClear = () => {
  store.clearMessages()
  message.success('对话已清空')
}

const handleClearAll = () => {
  store.clearAll()
  message.success('所有历史记录已清除')
}

const handleGenerateDocument = async () => {
  if (!similarQuery.value.trim()) {
    message.warning('请输入问题描述')
    return
  }

  loadingSimilar.value = true
  generationTaskId.value = null

  try {
    // 构建请求参数
    const request = {
      user_query: similarQuery.value,
      format: 'markdown',
      max_iterations: maxIterations.value,
      quality_threshold: qualityThreshold.value,
      retrieval_limit: retrievalLimit.value,
      use_thinking: useThinking_generate.value,
      similar_requirement_ids: []
    }

    // 根据检索模式设置参数
    if (documentMode_similar.value === 'single' && selectedGroupId_similar.value) {
      request.group_id = selectedGroupId_similar.value
    } else if (documentMode_similar.value === 'multiple' && selectedGroupIds_similar.value && selectedGroupIds_similar.value.length > 0) {
      request.group_ids = selectedGroupIds_similar.value
    } else if (documentMode_similar.value === 'all') {
      request.all_documents = true
    }

    const response = await generateRequirementDocumentAsync(request)

    // 调试：打印响应内容
    console.log('API响应:', response)
    
    // 注意：axios拦截器已经返回了response.data，所以response就是数据本身
    if (response && response.task_id) {
      generationTaskId.value = response.task_id
      message.success('文档生成任务已提交，请前往"任务管理"页面查看进度')
    } else {
      console.error('响应中没有task_id:', response)
      message.error('提交任务失败：未返回任务ID')
    }
  } catch (error) {
    console.error('生成需求文档失败:', error)
    message.error(`生成需求文档失败: ${error.response?.data?.detail || error.message || '未知错误'}`)
  } finally {
    loadingSimilar.value = false
  }
}

const goToTaskManagement = () => {
  router.push('/task-management')
}

const handleAnalyze = async () => {
  // 使用Tab 3的状态
  if (documentMode_analyze.value === 'single' && !selectedGroupId_analyze.value) {
    message.warning('请先选择文档')
    return
  }
  if (documentMode_analyze.value === 'multiple' && (!selectedGroupIds_analyze.value || selectedGroupIds_analyze.value.length < 2)) {
    message.warning('多文档模式需要至少选择2个文档')
    return
  }
  if (documentMode_analyze.value === 'all' && documents.value.length === 0) {
    message.warning('没有可用的文档')
    return
  }

  analyzing.value = true
  analysisResult.value = null

  try {
    // 根据模式选择group_id
    let groupId = null
    if (documentMode_analyze.value === 'single') {
      groupId = selectedGroupId_analyze.value
    } else if (documentMode_analyze.value === 'multiple' && selectedGroupIds_analyze.value && selectedGroupIds_analyze.value.length > 0) {
      // 多文档模式，使用第一个文档
      groupId = selectedGroupIds_analyze.value[0]
    }
    
    const response = await qaAnalyzeRequirement(groupId, selectedProvider_analyze.value)
    analysisResult.value = response
    message.success('分析完成')
  } catch (error) {
    console.error('需求分析失败:', error)
    message.error(`需求分析失败: ${error.message || '未知错误'}`)
  } finally {
    analyzing.value = false
  }
}

const viewDocument = (groupId) => {
  router.push({
    name: 'requirements-management',
    query: { document_id: groupId }
  })
}

// Tab 1 - 辅助函数（使用computed确保响应式更新）
const canSendMessage = computed(() => {
  if (documentMode_qa.value === 'single') {
    return !!selectedGroupId_qa.value
  } else if (documentMode_qa.value === 'multiple') {
    return selectedGroupIds_qa.value && selectedGroupIds_qa.value.length >= 2
  } else {
    // 全部文档模式
    return documents.value.length > 0
  }
})

const getInputPlaceholder = () => {
  if (documentMode_qa.value === 'single') {
    return '输入你的问题...（系统会自动从该文档的知识图谱检索相关信息）'
  } else if (documentMode_qa.value === 'multiple') {
    return '输入你的问题...（系统会自动从选中的多个文档的知识图谱检索相关信息）'
  } else {
    return '输入你的问题...（系统会自动从所有文档的知识图谱检索相关信息）'
  }
}

// Tab 3 - 辅助函数
const canSendMessage_analyze = () => {
  if (documentMode_analyze.value === 'single') {
    return !!selectedGroupId_analyze.value
  } else if (documentMode_analyze.value === 'multiple') {
    return selectedGroupIds_analyze.value && selectedGroupIds_analyze.value.length >= 2
  } else {
    // 全部文档模式
    return documents.value.length > 0
  }
}

// 检索设置相关辅助函数
const getSchemeColor = (scheme) => {
  const colors = {
    'default': 'blue',
    'enhanced': 'orange',
    'smart': 'purple',
    'fast': 'green'
  }
  return colors[scheme] || 'blue'
}

const getSchemeLabel = (scheme) => {
  const labels = {
    'default': '方案A（默认）',
    'enhanced': '方案B（增强）',
    'smart': '方案C（智能）',
    'fast': '方案D（快速）'
  }
  return labels[scheme] || '方案A（默认）'
}

const handleRetrievalSettingsConfirm = (settings) => {
  retrievalSettings.value = settings
  crossEncoderMode_qa.value = settings.scheme
  useThinking_qa.value = settings.useThinking
}

onMounted(() => {
  loadDocuments()
  // 加载保存的检索设置
  const saved = localStorage.getItem('retrievalSettings')
  if (saved) {
    try {
      const parsed = JSON.parse(saved)
      retrievalSettings.value = parsed
      crossEncoderMode_qa.value = parsed.scheme || 'default'
      if (parsed.useThinking !== undefined) {
        useThinking_qa.value = parsed.useThinking
      }
    } catch (e) {
      console.error('加载保存的检索设置失败:', e)
    }
  }
})
</script>

<style scoped>
</style>
