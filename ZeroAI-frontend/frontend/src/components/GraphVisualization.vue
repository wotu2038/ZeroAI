<template>
  <div ref="containerRef" style="width: 100%; height: 100%; position: relative; margin: 0; padding: 0">
    <div style="position: absolute; top: 10px; right: 10px; z-index: 10">
      <a-space>
        <a-button @click="refreshGraph">刷新</a-button>
        <a-button @click="zoomIn">放大</a-button>
        <a-button @click="zoomOut">缩小</a-button>
        <a-button @click="resetZoom">重置</a-button>
      </a-space>
    </div>
    <svg ref="svgRef" style="width: 100%; height: 100%"></svg>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as d3 from 'd3'
import { getGraphData } from '../api/graph'

const props = defineProps({
  data: {
    type: Object,
    default: null
  }
})

const containerRef = ref(null)
const svgRef = ref(null)
let simulation = null
let svg = null
let g = null
let zoom = null
let nodes = []
let links = []
let nodeElements = null
let linkElements = null
let linkPaths = null
let labelElements = null

// 实体类型推断函数（在函数外部定义，以便在多个地方使用）
const inferEntityType = (node) => {
  if (!node) return 'Entity'
  const name = node.properties?.name || ''
  const labels = node.labels || []
  
  // 优先检查是否是Episode节点
  if (labels.includes('Episodic')) {
    return 'Episodic'
  }
  
  // 如果 labels 中有具体类型（除了 Entity），使用它
  const specificLabel = labels.find(l => l !== 'Entity' && l !== 'Episodic')
  if (specificLabel) {
    return specificLabel
  }
  
  // 基于名称模式推断
  // 人物名称（通常是2-3个中文字符，且不包含"公司"、"集团"等）
  if (/^[\u4e00-\u9fa5]{2,4}$/.test(name) && 
      !name.includes('公司') && !name.includes('集团') && 
      !name.includes('大学') && !name.includes('城市') &&
      !name.includes('国家') && !name.includes('地区')) {
    // 检查是否是常见人名
    const commonNames = ['马云', '马化腾', '王五', '李小明', '张三', '李四']
    if (commonNames.includes(name)) {
      return 'Person'
    }
    // 检查是否与职位相关（通过关系推断）
    return 'Person' // 默认推断为人名
  }
  
  // 组织（包含"公司"、"集团"、"企业"等）
  if (name.includes('公司') || name.includes('集团') || 
      name.includes('企业') || name.includes('组织') ||
      name.includes('机构') || name.includes('协会')) {
    return 'Organization'
  }
  
  // 地点（包含"市"、"省"、"国"、"地区"等）
  if (name.includes('市') || name.includes('省') || 
      name.includes('国') || name.includes('地区') ||
      name.includes('州') || name === '中国' || name === '美国') {
    return 'Location'
  }
  
  // 大学
  if (name.includes('大学') || name.includes('学院') || name.includes('学校')) {
    return 'Organization'
  }
  
  // 职位/角色（包含"CEO"、"CTO"、"经理"、"主席"等）
  if (name.includes('CEO') || name.includes('CTO') || 
      name.includes('经理') || name.includes('主席') ||
      name.includes('总裁') || name.includes('总监') ||
      name.includes('官') || name.includes('长')) {
    return 'Concept'
  }
  
  // 技术/产品（包含"技术"、"产品"、"系统"等）
  if (name.includes('技术') || name.includes('产品') || 
      name.includes('系统') || name.includes('平台') ||
      name.includes('服务') || name.includes('应用')) {
    return 'Technology'
  }
  
  // 概念/抽象（其他）
  return 'Concept'
}

const initGraph = async () => {
  if (!svgRef.value) return

  // 清空SVG
  d3.select(svgRef.value).selectAll('*').remove()

  // 获取数据
  let graphData = props.data
  if (!graphData) {
    try {
      graphData = await getGraphData(200)
    } catch (error) {
      console.error('获取图数据失败:', error)
      return
    }
  }

  nodes = graphData.nodes || []
  links = graphData.edges || []
  
  // 确保所有节点ID都是字符串，并创建节点ID映射
  const nodeIdMap = new Map()
  nodes = nodes.map(node => {
    const nodeId = String(node.id)
    nodeIdMap.set(nodeId, node)
    return { ...node, id: nodeId }
  })
  
  // 确保所有边的source/target都是字符串，并且对应的节点存在
  links = links
    .map(link => {
      const sourceId = String(link.source)
      const targetId = String(link.target)
      
      // 检查source和target节点是否存在
      if (!nodeIdMap.has(sourceId)) {
        console.warn(`警告: 边的source节点不存在: ${sourceId}`, link)
        return null
      }
      if (!nodeIdMap.has(targetId)) {
        console.warn(`警告: 边的target节点不存在: ${targetId}`, link)
        return null
      }
      
      return {
        ...link,
        id: String(link.id),
        source: sourceId,
        target: targetId
      }
    })
    .filter(link => link !== null) // 过滤掉无效的边
  
  console.log(`初始化图谱: ${nodes.length} 个节点, ${links.length} 条边`)

  // 设置SVG
  const width = containerRef.value?.clientWidth || 800
  const height = containerRef.value?.clientHeight || 600

  svg = d3.select(svgRef.value)
    .attr('width', width)
    .attr('height', height)

  // 创建缩放
  zoom = d3.zoom()
    .scaleExtent([0.1, 4])
    .on('zoom', (event) => {
      g.attr('transform', event.transform)
    })

  svg.call(zoom)
    .on('click', (event) => {
      // 点击空白处清除高亮
      if (event.target === svg.node() || event.target.tagName === 'svg') {
        clearHighlight()
      }
    })

  // 创建主组
  g = svg.append('g')

  // 创建箭头标记（为不同关系类型创建不同的箭头）
  const defs = svg.append('defs')
  
  // 为每种关系名称创建不同颜色的箭头标记
  Object.keys(relationNameColors).forEach((relName) => {
    const marker = defs.append('marker')
      .attr('id', `arrowhead-${relName}`)
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 25)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', relationNameColors[relName] || '#999')
  })
  
  // 默认箭头标记
  const arrowMarker = defs.append('marker')
    .attr('id', 'arrowhead-default')
    .attr('viewBox', '0 -5 10 10')
    .attr('refX', 25)
    .attr('refY', 0)
    .attr('markerWidth', 6)
    .attr('markerHeight', 6)
    .attr('orient', 'auto')
    .append('path')
    .attr('d', 'M0,-5L10,0L0,5')
    .attr('fill', '#999')
  
  // 灰色箭头（用于非高亮边）
  const grayArrow = defs.append('marker')
    .attr('id', 'arrowhead-gray')
    .attr('viewBox', '0 -5 10 10')
    .attr('refX', 25)
    .attr('refY', 0)
    .attr('markerWidth', 6)
    .attr('markerHeight', 6)
    .attr('orient', 'auto')
    .append('path')
    .attr('d', 'M0,-5L10,0L0,5')
    .attr('fill', '#d9d9d9')
  
  // 绿色箭头（用于高亮边）
  const greenArrow = defs.append('marker')
    .attr('id', 'arrowhead-green')
    .attr('viewBox', '0 -5 10 10')
    .attr('refX', 25)
    .attr('refY', 0)
    .attr('markerWidth', 6)
    .attr('markerHeight', 6)
    .attr('orient', 'auto')
    .append('path')
    .attr('d', 'M0,-5L10,0L0,5')
    .attr('fill', '#52c41a')
  
  // 更亮的绿色箭头（用于最短路径边）
  const brightGreenArrow = defs.append('marker')
    .attr('id', 'arrowhead-green-bright')
    .attr('viewBox', '0 -5 10 10')
    .attr('refX', 25)
    .attr('refY', 0)
    .attr('markerWidth', 8)
    .attr('markerHeight', 8)
    .attr('orient', 'auto')
    .append('path')
    .attr('d', 'M0,-5L10,0L0,5')
    .attr('fill', '#73d13d')
  

  // 创建力导向图
  simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id(d => d.id).distance(100))
    .force('charge', d3.forceManyBody().strength(-300))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide().radius(30))
  
  // 创建连线（不设置颜色，由 updateHighlight 统一控制）
  linkElements = g.append('g')
    .attr('class', 'links')
    .selectAll('line')
    .data(links)
    .enter()
    .append('line')
    // 不在这里设置 stroke、marker-end 等颜色属性，由 updateHighlight() 统一控制
    .attr('data-edge-id', d => String(d.id))  // 添加 data 属性用于高亮匹配
    .style('cursor', 'pointer')
    .on('click', handleEdgeClick)
  
  // 创建透明的可点击区域（增加边的点击范围）
  linkPaths = g.append('g')
    .attr('class', 'link-paths')
    .selectAll('path')
    .data(links)
    .enter()
    .append('path')
    .attr('stroke', 'transparent')
    .attr('stroke-width', 20) // 增加点击区域
    .attr('fill', 'none')
    .style('cursor', 'pointer')
    .on('click', handleEdgeClick)

  // 创建节点（不设置颜色，由 updateHighlight 统一控制）
  nodeElements = g.append('g')
    .attr('class', 'nodes')
    .selectAll('circle')
    .data(nodes)
    .enter()
    .append('circle')
    .attr('r', d => {
      // 根据节点类型设置大小（使用推断的类型）
      const inferredType = inferEntityType(d)
      const typeSizes = {
        Person: 12,
        Organization: 15,
        Location: 10,
        Concept: 8,
        Event: 10,
        Product: 10,
        Technology: 10,
        Document: 8,
        Episodic: 10,  // Episode节点大小
        Requirement: 18,  // 需求节点更大，更明显
        Feature: 10,      // 功能点节点
        Module: 12,       // 模块节点
        Entity: 10
      }
      return typeSizes[inferredType] || 10
    })
    // 不在这里设置 fill、stroke 等颜色属性，由 updateHighlight() 统一控制
    .call(drag(simulation))
    .on('mouseover', handleNodeMouseOver)
    .on('mouseout', handleNodeMouseOut)
    .on('click', handleNodeClick)

  // 创建标签
  labelElements = g.append('g')
    .attr('class', 'labels')
    .selectAll('text')
    .data(nodes)
    .enter()
    .append('text')
    .text(d => {
      // Episode节点可能有name属性在properties中，或者直接在节点对象上
      if (d.labels && d.labels.includes('Episodic')) {
        return d.properties?.name || d.name || d.id
      }
      return d.properties?.name || d.name || d.id
    })
    .attr('font-size', '12px')
    .attr('dx', 15)
    .attr('dy', 4)
    .attr('fill', '#333')

  // 更新位置
  simulation.on('tick', () => {
    linkElements
      .attr('x1', d => d.source.x)
      .attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x)
      .attr('y2', d => d.target.y)
    
    // 更新透明路径的位置（用于增加点击区域）
    if (linkPaths) {
      linkPaths.attr('d', d => {
        const dx = d.target.x - d.source.x
        const dy = d.target.y - d.source.y
        const dr = Math.sqrt(dx * dx + dy * dy)
        return `M ${d.source.x},${d.source.y} L ${d.target.x},${d.target.y}`
      })
    }

    nodeElements
      .attr('cx', d => d.x)
      .attr('cy', d => d.y)

    labelElements
      .attr('x', d => d.x)
      .attr('y', d => d.y)
    
    // 在每次 tick 时重新应用高亮（确保颜色正确）
    updateHighlight()
  })
  
  // 初始化时应用高亮（如果有）
  updateHighlight()
}

const drag = (simulation) => {
  const dragstarted = (event, d) => {
    if (!event.active) simulation.alphaTarget(0.3).restart()
    d.fx = d.x
    d.fy = d.y
  }

  const dragged = (event, d) => {
    d.fx = event.x
    d.fy = event.y
  }

  const dragended = (event, d) => {
    if (!event.active) simulation.alphaTarget(0)
    d.fx = null
    d.fy = null
  }

  return d3.drag()
    .on('start', dragstarted)
    .on('drag', dragged)
    .on('end', dragended)
}

const handleNodeMouseOver = (event, d) => {
  d3.select(event.currentTarget)
    .attr('r', d => {
      const inferredType = inferEntityType(d)
      const typeSizes = {
        Person: 12,
        Organization: 15,
        Location: 10,
        Concept: 8,
        Event: 10,
        Product: 10,
        Technology: 10,
        Document: 8,
        Episodic: 10,  // Episode节点大小
        Entity: 10
      }
      return (typeSizes[inferredType] || 10) * 1.5
    })
}

const handleNodeMouseOut = (event, d) => {
  d3.select(event.currentTarget)
    .attr('r', d => {
      const inferredType = inferEntityType(d)
      const typeSizes = {
        Person: 12,
        Organization: 15,
        Location: 10,
        Concept: 8,
        Event: 10,
        Product: 10,
        Technology: 10,
        Document: 8,
        Episodic: 10,  // Episode节点大小
        Requirement: 18,  // 需求节点更大，更明显
        Feature: 10,      // 功能点节点
        Module: 12,       // 模块节点
        Entity: 10
      }
      return typeSizes[inferredType] || 10
    })
}

// 恢复 emit 事件，用于显示节点/边详情（使用弹窗或抽屉）
const emit = defineEmits(['nodeClick', 'edgeClick'])

const handleNodeClick = (event, d) => {
  if (event) event.stopPropagation()
  // 触发节点点击事件，由父组件处理（显示弹窗或抽屉）
  emit('nodeClick', d)
}

const handleEdgeClick = (event, d) => {
  if (event) event.stopPropagation()
  // 触发边点击事件，由父组件处理（显示弹窗或抽屉）
  emit('edgeClick', d)
}

const refreshGraph = async () => {
  // 清除高亮
  clearHighlight()
  await initGraph()
}

const zoomIn = () => {
  if (svg && zoom) {
    svg.transition().call(zoom.scaleBy, 1.5)
  }
}

const zoomOut = () => {
  if (svg && zoom) {
    svg.transition().call(zoom.scaleBy, 1 / 1.5)
  }
}

const resetZoom = () => {
  if (svg && zoom) {
    svg.transition().call(zoom.transform, d3.zoomIdentity)
  }
  // 重置时清除高亮
  clearHighlight()
}

// 高亮路径功能
let highlightedNodeIds = new Set()
let highlightedEdgeIds = new Set()
let shortestPathNodeIds = new Set()
let shortestPathEdgeIds = new Set()

// 关系颜色映射（在组件级别定义，供多个函数使用）
const relationNameColors = {
  'WORKS_FOR': '#1890ff',
  'RELATES_TO': '#52c41a',
  'KNOWS': '#faad14',
  'LOCATED_IN': '#722ed1',
  'OWNS': '#eb2f96',
  'CREATED': '#13c2c2',
  'PART_OF': '#f5222d',
  'INFLUENCES': '#fa8c16',
  'COLLABORATES_WITH': '#2f54eb',
  'MANAGES': '#a0d911',
  'FOUNDED': '#eb2f96',
  'DEVELOPS': '#722ed1',
  'HAS_POSITION': '#1890ff',
  'RESPONSIBLE_FOR': '#52c41a',
  'IS_A': '#faad14',
  'HEADQUARTERED_IN': '#722ed1',
  'HEADQUARTERS_OF': '#722ed1',
  'FOCUSES_ON': '#13c2c2',
  'IS_IN_COUNTRY': '#faad14'
}

// 获取关系名称
const getRelationName = (edge) => {
  if (!edge) return 'RELATES_TO'
  return edge.properties?.name || edge.name || edge.type || 'RELATES_TO'
}

// 获取关系类型的颜色
const getRelationColor = (edge) => {
  if (!edge) return '#999'
  const relName = getRelationName(edge)
  return relationNameColors[relName] || '#999'
}

// 获取关系类型的箭头标记ID
const getRelationMarker = (edge) => {
  if (!edge) return 'url(#arrowhead-default)'
  const relName = getRelationName(edge)
  if (relationNameColors[relName]) {
    return `url(#arrowhead-${relName})`
  }
  return 'url(#arrowhead-default)'
}

const highlightPaths = (nodeIds, edgeIds, shortestNodeIds, shortestEdgeIds) => {
  // 确保所有ID都是字符串类型
  highlightedNodeIds = new Set(nodeIds.map(id => String(id)))
  highlightedEdgeIds = new Set(edgeIds.map(id => String(id)))
  shortestPathNodeIds = new Set(shortestNodeIds.map(id => String(id)))
  shortestPathEdgeIds = new Set(shortestEdgeIds.map(id => String(id)))
  
  console.log('高亮路径:', {
    nodeIds: Array.from(highlightedNodeIds),
    edgeIds: Array.from(highlightedEdgeIds),
    shortestNodeIds: Array.from(shortestPathNodeIds),
    shortestEdgeIds: Array.from(shortestPathEdgeIds),
    hasHighlight: highlightedNodeIds.size > 0 || highlightedEdgeIds.size > 0
  })
  
  // 强制立即更新，并确保在下一个 tick 也更新
  updateHighlight()
  
  // 如果 simulation 正在运行，强制重启以确保样式更新
  if (simulation) {
    simulation.alpha(1).restart()
  }
}

const clearHighlight = () => {
  highlightedNodeIds.clear()
  highlightedEdgeIds.clear()
  shortestPathNodeIds.clear()
  shortestPathEdgeIds.clear()
  updateHighlight()
}

const updateHighlight = () => {
  if (!nodeElements || !linkElements) {
    console.warn('节点或边元素未准备好，无法更新高亮')
    return
  }
  
  // 如果有高亮，应用高亮样式；否则恢复原始样式
  const hasHighlight = highlightedNodeIds.size > 0 || highlightedEdgeIds.size > 0
  
  console.log('updateHighlight 调用:', {
    hasHighlight,
    nodeCount: highlightedNodeIds.size,
    edgeCount: highlightedEdgeIds.size,
    nodeElementsSize: nodeElements.size(),
    linkElementsSize: linkElements.size()
  })
  
  // 更新节点样式（强制设置所有属性）
  nodeElements
    .attr('fill', d => {
      const nodeId = String(d.id)
      const isHighlighted = highlightedNodeIds.has(nodeId)
      const isShortest = shortestPathNodeIds.has(nodeId)
      
      if (!hasHighlight) {
        // 没有高亮时，使用原始类型颜色
        const typeColors = {
          Person: '#1890ff',
          Organization: '#52c41a',
          Location: '#faad14',
          Concept: '#722ed1',
          Event: '#eb2f96',
          Product: '#13c2c2',
          Technology: '#2f54eb',
          Document: '#a0d911',
          Episodic: '#fa8c16',     // Episode节点：橙色，便于识别
          Requirement: '#ff4d4f',  // 需求节点：红色，更醒目
          Feature: '#fa8c16',      // 功能点节点：橙色
          Module: '#52c41a',       // 模块节点：绿色
          Entity: '#8c8c8c'
        }
        const inferredType = inferEntityType(d)
        return typeColors[inferredType] || typeColors['Entity']
      }
      
      if (!isHighlighted) {
        // 非高亮节点：灰色
        return '#d9d9d9'
      }
      
      if (isShortest) {
        // 最短路径节点：更亮的蓝色
        return '#40a9ff'
      }
      
      // 普通高亮节点：蓝色
      return '#1890ff'
    })
    .attr('opacity', d => {
      if (!hasHighlight) return 1
      const nodeId = String(d.id)
      const isHighlighted = highlightedNodeIds.has(nodeId)
      return isHighlighted ? 1 : 0.3  // 非高亮节点降低透明度
    })
    .attr('stroke', d => {
      const nodeId = String(d.id)
      const isHighlighted = highlightedNodeIds.has(nodeId)
      const isShortest = shortestPathNodeIds.has(nodeId)
      
      if (!hasHighlight) return '#fff'
      if (!isHighlighted) return '#ccc'
      if (isShortest) return '#1890ff'  // 最短路径节点边框更亮
      return '#fff'
    })
    .attr('stroke-width', d => {
      const nodeId = String(d.id)
      const isHighlighted = highlightedNodeIds.has(nodeId)
      const isShortest = shortestPathNodeIds.has(nodeId)
      
      if (!hasHighlight) return 2
      if (!isHighlighted) return 1
      return isShortest ? 3 : 2  // 最短路径节点加粗边框
    })
  
  // 更新边样式（强制设置所有属性）
  linkElements
    .attr('stroke', d => {
      const edgeId = String(d.id)
      const isHighlighted = highlightedEdgeIds.has(edgeId)
      const isShortest = shortestPathEdgeIds.has(edgeId)
      
      if (!hasHighlight) {
        // 没有高亮时，使用原始关系颜色
        return getRelationColor(d)
      }
      
      if (!isHighlighted) {
        // 非高亮边：灰色
        return '#d9d9d9'
      }
      
      if (isShortest) {
        // 最短路径边：更亮的绿色
        return '#73d13d'
      }
      
      // 普通高亮边：绿色
      return '#52c41a'
    })
    .attr('stroke-width', d => {
      const edgeId = String(d.id)
      const isHighlighted = highlightedEdgeIds.has(edgeId)
      const isShortest = shortestPathEdgeIds.has(edgeId)
      
      if (!hasHighlight) return 2
      if (!isHighlighted) return 1  // 非高亮边变细
      if (isShortest) return 4  // 最短路径边加粗
      return 3  // 普通高亮边（稍微加粗以突出显示）
    })
    .attr('opacity', d => {
      if (!hasHighlight) return 1
      const edgeId = String(d.id)
      const isHighlighted = highlightedEdgeIds.has(edgeId)
      return isHighlighted ? 1 : 0.2  // 非高亮边降低透明度
    })
    .attr('marker-end', d => {
      const edgeId = String(d.id)
      const isHighlighted = highlightedEdgeIds.has(edgeId)
      const isShortest = shortestPathEdgeIds.has(edgeId)
      
      if (!hasHighlight) {
        // 没有高亮时，使用原始箭头
        return getRelationMarker(d)
      }
      
      // 高亮时使用绿色箭头，非高亮时使用灰色箭头
      if (!isHighlighted) {
        return 'url(#arrowhead-gray)'
      }
      
      if (isShortest) {
        return 'url(#arrowhead-green-bright)'
      }
      
      return 'url(#arrowhead-green)'
    })
  
  // 更新标签样式
  if (labelElements) {
    labelElements
      .attr('opacity', d => {
        const nodeId = String(d.id)
        const isHighlighted = highlightedNodeIds.has(nodeId)
        return isHighlighted ? 1 : 0.3  // 非高亮节点标签也降低透明度
      })
  }
}

// 暴露方法给父组件
defineExpose({
  highlightPaths,
  clearHighlight,
  refreshGraph,
  zoomIn,
  zoomOut,
  resetZoom
})

// 监听窗口大小变化
const handleResize = () => {
  if (containerRef.value && svg) {
    const width = containerRef.value.clientWidth
    const height = containerRef.value.clientHeight
    svg.attr('width', width).attr('height', height)
    if (simulation) {
      simulation.force('center', d3.forceCenter(width / 2, height / 2))
      simulation.alpha(1).restart()
    }
  }
}

onMounted(() => {
  initGraph()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  if (simulation) {
    simulation.stop()
  }
  window.removeEventListener('resize', handleResize)
})

watch(() => props.data, () => {
  if (props.data) {
    initGraph()
  }
}, { deep: true })
</script>

<style scoped>
.links line {
  stroke-opacity: 0.6;
  cursor: pointer;
  pointer-events: none; /* 让line不接收点击，由path接收 */
}

.links line:hover {
  stroke-opacity: 1;
  stroke-width: 4;
  filter: brightness(1.2); /* 悬停时变亮 */
}

.link-paths path {
  pointer-events: all; /* 确保path可以接收点击 */
}

.nodes circle {
  cursor: pointer;
}

.nodes circle:hover {
  stroke-width: 3;
}

.labels text {
  pointer-events: none;
  user-select: none;
}
</style>

