/**
 * WebMotors Reconstructed + Embedded Analytics, Logistics & TCO - App Logic
 */

const state = {
  q: '',
  uf: '',
  marca: '',
  modelo: '',
  ano_min: '',
  ano_max: '',
  preco_max: 600000,
  km_max: 200000,
  deal_type: '',
  tipo_vendedor: '',
  sort: 'deal_desc',
  page: 1,
  limit: 18,
  travel: {
    user_city: localStorage.getItem('wm_user_city') || 'São Paulo',
    user_uf: localStorage.getItem('wm_user_uf') || 'SP',
    fuel_type: localStorage.getItem('wm_fuel_type') || 'GASOLINA',
    fuel_price: parseFloat(localStorage.getItem('wm_fuel_price') || '6.10'),
    km_per_liter: parseFloat(localStorage.getItem('wm_km_per_l') || '12.0'),
    toll_per_100km: parseFloat(localStorage.getItem('wm_toll') || '16.0'),
    extra_costs: parseFloat(localStorage.getItem('wm_extra') || '150.0'),
  }
};

let debounceTimer = null;
let depreciationChart = null;

// ==========================================================================
// 1. INICIALIZAÇÃO E CARREGAMENTO DE METADADOS
// ==========================================================================
document.addEventListener('DOMContentLoaded', async () => {
  updateNavTravelSummary();
  initEventListeners();
  await loadSummary();
  await loadFacets();
  await loadCities();
  await fetchCars();
});

function updateNavTravelSummary() {
  const el = document.getElementById('navTravelSummary');
  if (el) {
    el.innerHTML = `📍 Origem: <strong>${state.travel.user_city} (${state.travel.user_uf})</strong> • ${state.travel.fuel_type} (${state.travel.km_per_liter} km/l)`;
  }
}

async function loadSummary() {
  try {
    const res = await fetch('/api/summary');
    const data = await res.json();
    document.getElementById('tickerTotalVeiculos').innerText = data.total_veiculos.toLocaleString('pt-BR');
    document.getElementById('tickerTotalMarcas').innerText = data.total_marcas;
    document.getElementById('tickerPechinchas').innerHTML = `<strong>${data.total_pechinchas} oportunidades</strong> com preço >= 10% abaixo da média`;
  } catch (err) {
    console.error('Erro ao carregar summary:', err);
  }
}

const BRAND_LOGOS = {
  'CHEVROLET': 'https://cdn.simpleicons.org/chevrolet/1F242D',
  'VOLKSWAGEN': 'https://cdn.simpleicons.org/volkswagen/1F242D',
  'FIAT': 'https://cdn.simpleicons.org/fiat/E11138',
  'TOYOTA': 'https://cdn.simpleicons.org/toyota/E11138',
  'HYUNDAI': 'https://cdn.simpleicons.org/hyundai/1F242D',
  'HONDA': 'https://cdn.simpleicons.org/honda/E11138',
  'JEEP': 'https://cdn.simpleicons.org/jeep/1F242D',
  'RENAULT': 'https://cdn.simpleicons.org/renault/1F242D',
  'NISSAN': 'https://cdn.simpleicons.org/nissan/E11138',
  'FORD': 'https://cdn.simpleicons.org/ford/1F242D',
  'MITSUBISHI': 'https://cdn.simpleicons.org/mitsubishielectric/E11138',
  'SUZUKI': 'https://cdn.simpleicons.org/suzuki/E11138',
  'BMW': 'https://cdn.simpleicons.org/bmw/1F242D',
  'AUDI': 'https://cdn.simpleicons.org/audi/1F242D',
  'VOLVO': 'https://cdn.simpleicons.org/volvocars/1F242D',
  'PORSCHE': 'https://cdn.simpleicons.org/porsche/1F242D',
  'SUBARU': 'https://cdn.simpleicons.org/subaru/1F242D',
  'KIA': 'https://cdn.simpleicons.org/kia/1F242D',
  'PEUGEOT': 'https://cdn.simpleicons.org/peugeot/1F242D',
  'CITROEN': 'https://cdn.simpleicons.org/citroen/E11138',
  'CITROËN': 'https://cdn.simpleicons.org/citroen/E11138',
  'RAM': 'https://cdn.simpleicons.org/ram/1F242D'
};

function getBrandLogoUrl(marca) {
  const m = (marca || '').toUpperCase().trim();
  if (BRAND_LOGOS[m]) return BRAND_LOGOS[m];
  const slug = m.toLowerCase().replace(/[^a-z]/g, '');
  return `https://cdn.simpleicons.org/${slug}/1F242D`;
}

async function loadFacets() {
  try {
    const res = await fetch('/api/filters/facets');
    const data = await res.json();

    // Renderizar Seletor Visual de Marcas (Hero + Sidebar + Select)
    renderBrandSelectors(data.marcas || []);

    // Popular Anos
    const yearMin = document.getElementById('yearMinSelect');
    const yearMax = document.getElementById('yearMaxSelect');
    yearMin.innerHTML = '<option value="">De</option>';
    yearMax.innerHTML = '<option value="">Até</option>';
    for (let y = data.ano_max; y >= data.ano_min; y--) {
      yearMin.innerHTML += `<option value="${y}">${y}</option>`;
      yearMax.innerHTML += `<option value="${y}">${y}</option>`;
    }

    // Configurar limites de preço e km
    const priceRange = document.getElementById('priceRange');
    priceRange.max = Math.min(data.preco_max, 700000);
    priceRange.value = priceRange.max;
    state.preco_max = priceRange.value;
    updatePriceDisplay(priceRange.value);

  } catch (err) {
    console.error('Erro ao carregar facets:', err);
  }
}

function renderBrandSelectors(marcas) {
  // 1. Carrossel Hero com Logos
  const heroGrid = document.getElementById('heroBrandsGrid');
  if (heroGrid) {
    heroGrid.innerHTML = marcas.slice(0, 20).map(m => {
      const logo = getBrandLogoUrl(m.marca);
      const isActive = state.marca.toUpperCase() === m.marca.toUpperCase();
      return `
        <div class="wm-brand-card-item ${isActive ? 'active' : ''}" data-brand="${m.marca}" onclick="selectBrand('${m.marca}')">
          <img src="${logo}" alt="${m.marca}" class="wm-brand-logo-icon" onerror="this.src='https://cdn.simpleicons.org/car/1F242D'">
          <span class="wm-brand-name-text">${m.marca}</span>
          <span class="wm-brand-count-badge">${m.total}</span>
        </div>
      `;
    }).join('');
  }

  // 2. Mini Grid na Sidebar com as 8 Principais
  const sidebarGrid = document.getElementById('sidebarBrandGrid');
  if (sidebarGrid) {
    const topSidebar = marcas.slice(0, 8);
    sidebarGrid.innerHTML = topSidebar.map(m => {
      const logo = getBrandLogoUrl(m.marca);
      const isActive = state.marca.toUpperCase() === m.marca.toUpperCase();
      return `
        <div class="wm-sidebar-brand-btn ${isActive ? 'active' : ''}" onclick="selectBrand('${m.marca}')" title="${m.marca}">
          <img src="${logo}" alt="${m.marca}" class="wm-sidebar-brand-icon" onerror="this.src='https://cdn.simpleicons.org/car/1F242D'">
          <span>${m.marca}</span>
        </div>
      `;
    }).join('');
  }

  // 3. Dropdown Completo com Todas as Marcas
  const brandSelect = document.getElementById('brandSelect');
  if (brandSelect) {
    brandSelect.innerHTML = '<option value="">Todas as Marcas</option>';
    marcas.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m.marca;
      opt.innerText = `${m.marca} (${m.total})`;
      if (state.marca.toUpperCase() === m.marca.toUpperCase()) opt.selected = true;
      brandSelect.appendChild(opt);
    });
  }
}

async function selectBrand(marca) {
  // Se clicar na mesma marca ativa, desseleciona
  if (state.marca && state.marca.toUpperCase() === marca.toUpperCase()) {
    state.marca = '';
    state.modelo = '';
  } else {
    state.marca = marca;
    state.modelo = '';
  }
  state.page = 1;

  // Atualizar visual dos botões
  document.querySelectorAll('.wm-brand-card-item').forEach(b => {
    b.classList.toggle('active', b.getAttribute('data-brand') === state.marca);
  });
  document.querySelectorAll('.wm-sidebar-brand-btn').forEach(b => {
    b.classList.toggle('active', b.getAttribute('title') === state.marca);
  });

  const brandSelect = document.getElementById('brandSelect');
  if (brandSelect) brandSelect.value = state.marca;

  // Carregar e exibir modelos da marca
  await updateModelsForBrand(state.marca);

  fetchCars();
}

async function updateModelsForBrand(marca) {
  const heroModelsBar = document.getElementById('heroModelsBar');
  const heroChips = document.getElementById('heroModelsChips');
  const sidebarChips = document.getElementById('sidebarModelsChips');
  const modelSelect = document.getElementById('modelSelect');

  if (!marca) {
    if (heroModelsBar) heroModelsBar.classList.remove('visible');
    if (heroChips) heroChips.innerHTML = '';
    if (sidebarChips) sidebarChips.innerHTML = '';
    if (modelSelect) {
      modelSelect.innerHTML = '<option value="">Selecione uma marca primeiro</option>';
      modelSelect.disabled = true;
    }
    return;
  }

  if (modelSelect) {
    modelSelect.disabled = false;
    modelSelect.innerHTML = '<option value="">Todos os Modelos</option>';
  }

  try {
    const res = await fetch(`/api/filters/models?marca=${encodeURIComponent(marca)}`);
    const data = await res.json();
    const models = data.models || [];

    if (models.length > 0) {
      if (heroModelsBar) heroModelsBar.classList.add('visible');
      const titleEl = document.getElementById('heroModelsTitle');
      if (titleEl) titleEl.innerText = `Modelos ${marca}:`;

      // Chips no Hero
      if (heroChips) {
        heroChips.innerHTML = models.map(m => `
          <button class="wm-model-chip ${state.modelo === m.modelo ? 'active' : ''}" onclick="selectModel('${m.modelo}')">
            ${m.modelo} <span style="opacity: 0.75; font-size: 0.72rem;">(${m.total})</span>
          </button>
        `).join('');
      }

      // Chips na Sidebar
      if (sidebarChips) {
        sidebarChips.innerHTML = models.slice(0, 8).map(m => `
          <button class="wm-model-chip ${state.modelo === m.modelo ? 'active' : ''}" onclick="selectModel('${m.modelo}')">
            ${m.modelo}
          </button>
        `).join('');
      }

      // Dropdown de Modelo
      if (modelSelect) {
        models.forEach(m => {
          const opt = document.createElement('option');
          opt.value = m.modelo;
          opt.innerText = `${m.modelo} (${m.total})`;
          if (state.modelo === m.modelo) opt.selected = true;
          modelSelect.appendChild(opt);
        });
      }
    } else {
      if (heroModelsBar) heroModelsBar.classList.remove('visible');
    }
  } catch (err) {
    console.error('Erro ao buscar modelos:', err);
  }
}

function selectModel(modelo) {
  if (state.modelo === modelo) {
    state.modelo = '';
  } else {
    state.modelo = modelo;
  }
  state.page = 1;

  // Atualizar chips ativos
  document.querySelectorAll('.wm-model-chip').forEach(c => {
    const text = c.innerText.split('(')[0].trim();
    c.classList.toggle('active', text === state.modelo);
  });

  const modelSelect = document.getElementById('modelSelect');
  if (modelSelect) modelSelect.value = state.modelo;

  fetchCars();
}

async function loadCities() {
  try {
    const res = await fetch('/api/cities');
    const data = await res.json();
    const list = document.getElementById('citiesList');
    if (list && data.cities) {
      list.innerHTML = data.cities.map(c => `<option value="${c}">`).join('');
    }
  } catch (err) {
    console.error('Erro ao carregar cidades:', err);
  }
}

// ==========================================================================
// 2. BUSCA E RENDERIZAÇÃO DE ANÚNCIOS (CARDS WEBMOTORS COM VIAGEM E TCO)
// ==========================================================================
async function fetchCars() {
  const grid = document.getElementById('carGrid');
  grid.innerHTML = `
    <div style="grid-column: 1/-1; text-align: center; padding: 60px 20px; color: var(--text-muted);">
      <i class="fa-solid fa-circle-notch fa-spin fa-2x" style="color: var(--wm-red); margin-bottom: 12px;"></i>
      <p style="font-weight: 600;">Calculando as melhores ofertas, custos de viagem e manutenção...</p>
    </div>
  `;

  const params = new URLSearchParams();
  if (state.q) params.append('q', state.q);
  if (state.uf) params.append('uf', state.uf);
  if (state.marca) params.append('marca', state.marca);
  if (state.modelo) params.append('modelo', state.modelo);
  if (state.ano_min) params.append('ano_min', state.ano_min);
  if (state.ano_max) params.append('ano_max', state.ano_max);
  if (state.preco_max) params.append('preco_max', state.preco_max);
  if (state.km_max) params.append('km_max', state.km_max);
  if (state.deal_type) params.append('deal_type', state.deal_type);
  if (state.tipo_vendedor) params.append('tipo_vendedor', state.tipo_vendedor);
  params.append('sort', state.sort);
  params.append('page', state.page);
  params.append('limit', state.limit);

  // Parâmetros de Viagem & Origem do Usuário
  params.append('user_city', state.travel.user_city);
  params.append('user_uf', state.travel.user_uf);
  params.append('fuel_type', state.travel.fuel_type);
  params.append('fuel_price', state.travel.fuel_price);
  params.append('km_per_liter', state.travel.km_per_liter);
  params.append('toll_per_100km', state.travel.toll_per_100km);
  params.append('extra_costs', state.travel.extra_costs);

  try {
    const res = await fetch(`/api/cars?${params.toString()}`);
    const data = await res.json();

    document.getElementById('totalCarsCount').innerText = data.total.toLocaleString('pt-BR');

    if (!data.items || data.items.length === 0) {
      grid.innerHTML = `
        <div style="grid-column: 1/-1; text-align: center; padding: 60px 20px; background: #FFFFFF; border-radius: 16px; border: 1px solid var(--border-subtle);">
          <i class="fa-solid fa-car-side fa-3x" style="color: var(--text-light); margin-bottom: 16px;"></i>
          <h3 style="font-weight: 800; font-size: 1.25rem;">Nenhum carro encontrado com esses filtros</h3>
          <p style="color: var(--text-muted); margin-top: 6px;">Tente alterar os termos de busca ou remover alguns filtros laterais.</p>
          <button onclick="resetFilters()" class="wm-btn-sell" style="margin-top: 18px; padding: 8px 20px;">Limpar Todos os Filtros</button>
        </div>
      `;
      renderPagination(0, 1);
      return;
    }

    grid.innerHTML = data.items.map(car => renderCarCard(car)).join('');
    renderPagination(data.total_pages, data.page);

  } catch (err) {
    grid.innerHTML = `<div style="grid-column: 1/-1; color: var(--wm-red); text-align: center; padding: 40px;">Erro ao carregar anúncios: ${err}</div>`;
  }
}

function renderCarCard(car) {
  const badge = car.deal_badge;
  const photo = car.foto_url || 'https://image.webmotors.com.br/_fotos/AnuncioUsados/G/placeholder.jpg';
  const precoFmt = car.preco.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 });
  const parcelaFmt = car.parcela_estimada > 0 ? car.parcela_estimada.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }) : '';
  const kmFmt = car.quilometragem > 0 ? `${car.quilometragem.toLocaleString('pt-BR')} km` : '0 km';

  // Badge de Oportunidade
  const badgeHtml = `
    <div class="wm-deal-ribbon ${badge.color}">
      <i class="fa-solid fa-circle-check"></i> ${badge.label} (${badge.sub})
    </div>
  `;

  // Alerta de Redução de Preço
  const priceDropHtml = car.price_drop ? `
    <div class="wm-price-drop-badge">
      <i class="fa-solid fa-arrow-down"></i> ${car.price_drop.texto}
    </div>
  ` : '';

  // Spread bar
  const diffClass = car.desconto_pct >= 5 ? 'good' : (car.desconto_pct >= -5 ? 'fair' : 'above');
  const diffText = car.desconto_pct > 0 
    ? `Economia de ${(car.preco_mercado - car.preco).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 })}`
    : `Média de Mercado: ${car.preco_mercado.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 })}`;

  // Informações de Viagem & Logística
  const v = car.viagem;
  const tripWidgetHtml = `
    <div class="wm-card-trip-widget">
      <div class="wm-trip-row-top">
        <span><i class="fa-solid fa-route"></i> ${v.distancia_km} km de você (${v.distancia_ida_volta_km || v.distancia_km} km ida/volta)</span>
        <span class="wm-trip-cost-tag">Viagem: R$ ${v.custo_total_viagem.toLocaleString('pt-BR')}</span>
      </div>
      <div class="wm-trip-verdict-banner ${v.veredito.cor}">
        <i class="fa-solid fa-flag-checkered"></i> ${v.veredito.titulo}
      </div>
    </div>
  `;

  // Informações de Custo de Posse (TCO)
  const tco = car.tco;
  const tcoWidgetHtml = `
    <div class="wm-card-tco-widget" title="Seguro: R$ ${tco.detalhamento_mensal.seguro}/mês • IPVA: R$ ${tco.detalhamento_mensal.ipva}/mês • Manutenção: R$ ${tco.detalhamento_mensal.manutencao}/mês • Combustível: R$ ${tco.detalhamento_mensal.combustivel}/mês">
      <span class="wm-card-tco-title"><i class="fa-solid fa-wrench"></i> Custo de Manter:</span>
      <span class="wm-card-tco-val">R$ ${tco.custo_total_mensal.toLocaleString('pt-BR')} / mês</span>
    </div>
  `;

  return `
    <div class="wm-card">
      <div class="wm-card-media">
        ${badgeHtml}
        ${priceDropHtml}
        <button class="wm-favorite-btn" title="Salvar como Favorito" onclick="toggleFavorite(this, event)">
          <i class="fa-regular fa-heart"></i>
        </button>
        <img 
          src="${photo}" 
          alt="${car.marca} ${car.modelo}" 
          class="wm-card-img" 
          loading="lazy"
          onerror="this.src='https://images.unsplash.com/photo-1542282088-72c9c27ed0cd?w=600&auto=format&fit=crop&q=80'"
        />
      </div>

      <div class="wm-card-body">
        <div class="wm-card-title-group">
          <h2 class="wm-card-make-model">${car.marca} ${car.modelo}</h2>
          <div class="wm-card-version" title="${car.versao}">${car.versao || 'Versão Padrão'}</div>
        </div>

        <div class="wm-card-price-row">
          <div class="wm-card-price">${precoFmt}</div>
          ${parcelaFmt ? `<div class="wm-card-installment">ou 48x de <strong>${parcelaFmt}</strong></div>` : ''}
        </div>

        <!-- Indicador de Analytics Embutido no Card -->
        <div class="wm-spread-bar-container">
          <span class="wm-spread-text">Avaliação de Mercado:</span>
          <span class="wm-spread-diff ${diffClass}">${diffText}</span>
        </div>

        <!-- Widgets de Logística de Viagem & Custo de Manter (TCO) -->
        ${tripWidgetHtml}
        ${tcoWidgetHtml}

        <div class="wm-card-specs">
          <span><i class="fa-regular fa-calendar"></i> ${car.ano_fabricacao}/${car.ano_modelo}</span>
          <span><i class="fa-solid fa-gauge-high"></i> ${kmFmt}</span>
          <span class="wm-card-location"><i class="fa-solid fa-location-dot"></i> ${car.cidade ? `${car.cidade} - ${car.estado}` : car.estado}</span>
        </div>

        <div class="wm-card-actions">
          <button class="wm-btn-details" onclick="openCarModal('${car.id_anuncio}')">
            Ver Detalhes
          </button>
          <button class="wm-btn-analytics" onclick="openCarModal('${car.id_anuncio}')">
            <i class="fa-solid fa-chart-simple"></i> Raio-X & Viagem
          </button>
        </div>
      </div>
    </div>
  `;
}

// ==========================================================================
// 3. MODAL DE DETALHES DO VEÍCULO & RAIO-X ANALÍTICO + VIAGEM + TCO
// ==========================================================================
async function openCarModal(id_anuncio) {
  const modal = document.getElementById('carModal');
  const modalBody = document.getElementById('modalBody');

  modalBody.innerHTML = `
    <div style="grid-column: 1/-1; text-align: center; padding: 80px 20px;">
      <i class="fa-solid fa-circle-notch fa-spin fa-3x" style="color: var(--wm-red); margin-bottom: 16px;"></i>
      <p style="font-weight: 700; font-size: 1.1rem;">Calculando Raio-X de Viagem, Manutenção e Mercado...</p>
    </div>
  `;
  modal.classList.add('open');

  const params = new URLSearchParams();
  params.append('user_city', state.travel.user_city);
  params.append('user_uf', state.travel.user_uf);
  params.append('fuel_type', state.travel.fuel_type);
  params.append('fuel_price', state.travel.fuel_price);
  params.append('km_per_liter', state.travel.km_per_liter);
  params.append('toll_per_100km', state.travel.toll_per_100km);
  params.append('extra_costs', state.travel.extra_costs);

  try {
    const res = await fetch(`/api/cars/${id_anuncio}?${params.toString()}`);
    if (!res.ok) throw new Error('Não foi possível carregar os detalhes do carro.');
    const data = await res.json();
    const c = data.car;
    const a = data.analytics;
    const v = a.viagem;
    const t = a.tco;

    const precoFmt = c.preco.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 });
    const mediaFmt = a.media_mercado.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 });
    const kmFmt = c.quilometragem > 0 ? `${c.quilometragem.toLocaleString('pt-BR')} km` : '0 km';
    const foto = c.foto_url || 'https://images.unsplash.com/photo-1542282088-72c9c27ed0cd?w=900&auto=format&fit=crop&q=80';

    modalBody.innerHTML = `
      <!-- Coluna da Esquerda: Galeria e Ficha -->
      <div>
        <div class="wm-modal-gallery">
          <img src="${foto}" alt="${c.marca} ${c.modelo}" class="wm-modal-img" onerror="this.src='https://images.unsplash.com/photo-1542282088-72c9c27ed0cd?w=900&auto=format&fit=crop&q=80'" />
        </div>

        <div class="wm-modal-specs-grid">
          <div class="wm-spec-item">
            <span class="wm-spec-label">Ano de Fabricação / Modelo</span>
            <span class="wm-spec-value">${c.ano_fabricacao} / ${c.ano_modelo}</span>
          </div>
          <div class="wm-spec-item">
            <span class="wm-spec-label">Quilometragem</span>
            <span class="wm-spec-value">${kmFmt}</span>
          </div>
          <div class="wm-spec-item">
            <span class="wm-spec-label">Localização do Estoque</span>
            <span class="wm-spec-value">${c.cidade ? `${c.cidade} - ${c.estado}` : c.estado}</span>
          </div>
          <div class="wm-spec-item">
            <span class="wm-spec-label">Tipo de Vendedor</span>
            <span class="wm-spec-value">${c.tipo_vendedor || 'Concessionária'}</span>
          </div>
        </div>
      </div>

      <!-- Coluna da Direita: Preço, Vendedor e Ações -->
      <div style="display: flex; flex-direction: column;">
        <div style="display: flex; align-items: center; gap: 8px;">
          <span class="wm-logo-badge" style="font-size: 0.8rem; padding: 2px 8px;">${c.marca}</span>
          <span style="font-size: 0.85rem; color: var(--text-muted); font-weight: 600;">ID #${c.id_anuncio}</span>
        </div>

        <h1 style="font-size: 1.6rem; font-weight: 800; text-transform: uppercase; margin-top: 6px;">
          ${c.marca} ${c.modelo}
        </h1>
        <div style="color: var(--text-muted); font-size: 0.88rem; margin-bottom: 12px;">
          ${c.versao}
        </div>

        <div class="wm-modal-price">${precoFmt}</div>

        <!-- Card de Comparativo com Mercado -->
        <div style="background: ${a.spread_pct >= 5 ? '#ECFDF5' : '#EFF6FF'}; border: 1px solid ${a.spread_pct >= 5 ? '#A7F3D0' : '#BFDBFE'}; border-radius: 10px; padding: 12px 16px; margin-bottom: 16px;">
          <div style="font-size: 0.85rem; font-weight: 700; color: ${a.spread_pct >= 5 ? '#065F46' : '#1E40AF'}; display: flex; align-items: center; gap: 6px;">
            <i class="fa-solid fa-chart-line"></i>
            ${a.spread_pct > 0 ? `Economia de ${a.spread_pct}% contra a média` : `Dentro do valor de mercado`}
          </div>
          <div style="font-size: 0.8rem; color: #4B5563; margin-top: 4px;">
            Média regional para ${c.modelo} ${c.ano_modelo}: <strong>${mediaFmt}</strong> (base de ${a.qtd_amostra} carros)
          </div>
        </div>

        <!-- Botões de Proposta e Contato -->
        <div style="display: flex; flex-direction: column; gap: 10px; margin-top: auto;">
          <a href="https://wa.me/?text=Ol%C3%A1,%20tenho%20interesse%20no%20${encodeURIComponent(c.marca + ' ' + c.modelo)}%20anunciado%20por%20${encodeURIComponent(precoFmt)}" target="_blank" class="wm-btn-sell" style="text-align: center; text-decoration: none; display: flex; align-items: center; justify-content: center; gap: 8px; font-size: 1rem;">
            <i class="fa-brands fa-whatsapp fa-lg"></i> Falar com o Vendedor
          </a>
          ${c.url_anuncio ? `
            <a href="${c.url_anuncio}" target="_blank" class="wm-btn-details" style="text-align: center; text-decoration: none; padding: 10px;">
              <i class="fa-solid fa-arrow-up-right-from-square"></i> Ver Anúncio Original na WebMotors
            </a>
          ` : ''}
        </div>
      </div>

      <!-- PAINEL EMBUTIDO DE ANALYTICS & LOGÍSTICA & TCO -->
      <div class="wm-analytics-drawer">
        
        <!-- SEÇÃO 1: CALCULADORA DE VIAGEM DE BUSCA -->
        <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 18px; margin-bottom: 20px;">
          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
            <div style="font-size: 1.05rem; font-weight: 800; color: #0F172A; display: flex; align-items: center; gap: 8px;">
              <i class="fa-solid fa-route" style="color: var(--wm-red);"></i> Logística de Viagem: Vale a pena buscar em ${c.cidade || c.estado}?
            </div>
            <div class="wm-trip-verdict-banner ${v.veredito.cor}" style="font-size: 0.82rem; padding: 6px 12px;">
              <i class="fa-solid fa-flag-checkered"></i> ${v.veredito.titulo}
            </div>
          </div>
          <p style="font-size: 0.84rem; color: var(--text-muted); margin-top: 6px;">
            Sua Origem: <strong>${state.travel.user_city} (${state.travel.user_uf})</strong> ➔ Destino do Carro: <strong>${c.cidade ? `${c.cidade} - ${c.estado}` : c.estado}</strong>
          </p>

          <div class="wm-travel-breakdown-grid">
            <div class="wm-breakdown-box">
              <span class="wm-breakdown-lbl">Distância Total</span>
              <span class="wm-breakdown-val">${v.distancia_km} km <small style="font-size: 0.7rem; color: var(--text-muted);">(${v.distancia_ida_volta_km || v.distancia_km} km ida/volta)</small></span>
            </div>
            <div class="wm-breakdown-box">
              <span class="wm-breakdown-lbl">Combustível (${v.litros_combustivel || 0} L)</span>
              <span class="wm-breakdown-val">R$ ${(v.custo_combustivel || 0).toLocaleString('pt-BR')}</span>
            </div>
            <div class="wm-breakdown-box">
              <span class="wm-breakdown-lbl">Pedágios Estimados</span>
              <span class="wm-breakdown-val">R$ ${(v.custo_pedagios || 0).toLocaleString('pt-BR')}</span>
            </div>
            <div class="wm-breakdown-box" style="border-color: #A7F3D0; background: #ECFDF5;">
              <span class="wm-breakdown-lbl" style="color: #065F46;">Custo Total da Viagem</span>
              <span class="wm-breakdown-val" style="color: #065F46;">R$ ${v.custo_total_viagem.toLocaleString('pt-BR')}</span>
            </div>
          </div>

          <div style="margin-top: 12px; background: #F8FAFC; border-radius: 8px; padding: 10px 14px; font-size: 0.82rem; display: flex; justify-content: space-between; align-items: center;">
            <span>Preço Efetivo do Carro na sua Garagem (Carro + Viagem):</span>
            <strong style="font-size: 1rem; color: #0F172A;">R$ ${v.preco_total_efetivo.toLocaleString('pt-BR')}</strong>
          </div>
        </div>

        <!-- SEÇÃO 2: CUSTO TOTAL DE POSSE (TCO - SEGURO, IPVA, MANUTENÇÃO) -->
        <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 18px; margin-bottom: 20px;">
          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
            <div style="font-size: 1.05rem; font-weight: 800; color: #0F172A; display: flex; align-items: center; gap: 8px;">
              <i class="fa-solid fa-wrench" style="color: #D97706;"></i> Custo de Manter o Carro (TCO Anual e Mensal)
            </div>
            <div style="font-size: 1.15rem; font-weight: 800; color: #B45309; background: #FEF3C7; padding: 4px 12px; border-radius: 6px;">
              R$ ${t.custo_total_mensal.toLocaleString('pt-BR')} / mês <small style="font-size: 0.75rem; font-weight: 600;">(R$ ${t.custo_total_anual.toLocaleString('pt-BR')}/ano)</small>
            </div>
          </div>
          <p style="font-size: 0.82rem; color: var(--text-muted); margin-top: 6px;">
            Estimativa calculada com base na categoria ${c.marca}, alíquota do estado ${c.estado}, idade de ${2026 - c.ano_modelo} anos e rodagem média de 1.000 km/mês.
          </p>

          <div class="wm-tco-grid-4">
            <div class="wm-tco-item-card">
              <div class="wm-tco-item-header"><i class="fa-solid fa-shield-halved"></i> Seguro Auto Médio</div>
              <div class="wm-tco-item-monthly">R$ ${t.detalhamento_mensal.seguro.toLocaleString('pt-BR')} <small style="font-size: 0.7rem;">/mês</small></div>
              <div class="wm-tco-item-annual">R$ ${t.detalhamento_anual.seguro.toLocaleString('pt-BR')} / ano (${t.detalhamento_anual.categoria_seguro})</div>
            </div>

            <div class="wm-tco-item-card">
              <div class="wm-tco-item-header"><i class="fa-solid fa-file-invoice-dollar"></i> IPVA Estimado</div>
              <div class="wm-tco-item-monthly">R$ ${t.detalhamento_mensal.ipva.toLocaleString('pt-BR')} <small style="font-size: 0.7rem;">/mês</small></div>
              <div class="wm-tco-item-annual">${t.detalhamento_anual.ipva_isento ? 'Isento por idade' : `R$ ${t.detalhamento_anual.ipva.toLocaleString('pt-BR')} / ano`}</div>
            </div>

            <div class="wm-tco-item-card">
              <div class="wm-tco-item-header"><i class="fa-solid fa-gears"></i> Manutenção & Pneus</div>
              <div class="wm-tco-item-monthly">R$ ${t.detalhamento_mensal.manutencao.toLocaleString('pt-BR')} <small style="font-size: 0.7rem;">/mês</small></div>
              <div class="wm-tco-item-annual">R$ ${t.detalhamento_anual.manutencao.toLocaleString('pt-BR')} / ano (preventiva)</div>
            </div>

            <div class="wm-tco-item-card">
              <div class="wm-tco-item-header"><i class="fa-solid fa-gas-pump"></i> Combustível Médio</div>
              <div class="wm-tco-item-monthly">R$ ${t.detalhamento_mensal.combustivel.toLocaleString('pt-BR')} <small style="font-size: 0.7rem;">/mês</small></div>
              <div class="wm-tco-item-annual">R$ ${t.detalhamento_anual.combustivel.toLocaleString('pt-BR')} / ano (1.000 km/mês)</div>
            </div>
          </div>
        </div>

        <!-- SEÇÃO 3: CURVA DE DEPRECIAÇÃO & ARBITRAGEM -->
        <div class="wm-analytics-header">
          <div class="wm-analytics-title">
            <i class="fa-solid fa-chart-pie" style="color: var(--wm-red);"></i>
            Raio-X de Mercado: ${c.marca} ${c.modelo}
          </div>
          <span style="font-size: 0.8rem; color: var(--text-muted); font-weight: 600;">
            Dados calculados em tempo real sobre a base nacional
          </span>
        </div>

        <div class="wm-analytics-grid-2">
          <!-- Gráfico de Curva de Depreciação -->
          <div class="wm-chart-card">
            <div class="wm-chart-title">
              <i class="fa-solid fa-chart-line"></i> Curva de Preço Médio por Ano (Depreciação)
            </div>
            <div style="height: 220px;">
              <canvas id="depreciationCanvas"></canvas>
            </div>
          </div>

          <!-- Tabela de Arbitragem Interestadual -->
          <div class="wm-chart-card">
            <div class="wm-chart-title">
              <i class="fa-solid fa-earth-americas"></i> Comparativo de Preço por Estado (Arbitragem)
            </div>
            <div style="overflow-x: auto; max-height: 220px;">
              <table class="wm-arb-table">
                <thead>
                  <tr>
                    <th>Estado</th>
                    <th>Preço Médio</th>
                    <th>Comparado a Este</th>
                  </tr>
                </thead>
                <tbody>
                  ${a.arbitragem_regional && a.arbitragem_regional.length > 0 
                    ? a.arbitragem_regional.map(arb => {
                        const diff = arb.diferenca_vs_este;
                        const diffColor = diff > 0 ? '#059669' : (diff < 0 ? '#D97706' : '#6B7280');
                        const diffTxt = diff > 0 
                          ? `+R$ ${Math.abs(diff).toLocaleString('pt-BR')} (Mais caro lá)`
                          : (diff < 0 ? `-R$ ${Math.abs(diff).toLocaleString('pt-BR')} (Mais barato lá)` : 'Mesmo valor');
                        return `
                          <tr>
                            <td><strong>${arb.uf}</strong> (${arb.total} carros)</td>
                            <td>R$ ${arb.preco_medio.toLocaleString('pt-BR')}</td>
                            <td style="color: ${diffColor}; font-weight: 700;">${diffTxt}</td>
                          </tr>
                        `;
                      }).join('')
                    : '<tr><td colspan="3" style="text-align: center; color: var(--text-muted);">Amostra única registrada neste estado.</td></tr>'
                  }
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <!-- Histórico de Alterações de Preço deste Anúncio -->
        ${a.historico_precos && a.historico_precos.length > 0 ? `
          <div style="margin-top: 16px; background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 12px 16px;">
            <div style="font-weight: 700; font-size: 0.88rem; color: #1E293B; margin-bottom: 8px;">
              <i class="fa-solid fa-clock-rotate-left" style="color: var(--wm-red);"></i> Histórico de Alterações de Preço deste Carro
            </div>
            <div style="display: flex; gap: 16px; flex-wrap: wrap;">
              ${a.historico_precos.map(h => `
                <div style="background: var(--bg-main); padding: 8px 12px; border-radius: 6px; font-size: 0.8rem;">
                  <span style="color: var(--text-muted);">${h.data}:</span>
                  <span style="text-decoration: line-through; color: #9CA3AF;">R$ ${h.preco_anterior.toLocaleString('pt-BR')}</span>
                  <strong style="color: ${h.diferenca < 0 ? '#059669' : '#DC2626'};"> ➔ R$ ${h.preco_novo.toLocaleString('pt-BR')}</strong>
                </div>
              `).join('')}
            </div>
          </div>
        ` : ''}

      </div>
    `;

    // Renderizar Gráfico de Depreciação no Canvas
    if (a.curva_depreciacao && a.curva_depreciacao.length > 1) {
      renderDepreciationChart(a.curva_depreciacao, c.ano_modelo, c.preco);
    } else {
      const canvasEl = document.getElementById('depreciationCanvas');
      if (canvasEl && canvasEl.parentElement) {
        canvasEl.parentElement.innerHTML = `
          <div style="display: flex; align-items: center; justify-content: center; height: 100%; color: var(--text-muted); font-size: 0.85rem;">
            Amostra insuficiente de anos para traçar a curva deste modelo.
          </div>
        `;
      }
    }

  } catch (err) {
    modalBody.innerHTML = `<div style="color: var(--wm-red); text-align: center; padding: 40px;">${err.message}</div>`;
  }
}

function renderDepreciationChart(curva, anoAtual, precoAtual) {
  const canvas = document.getElementById('depreciationCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (depreciationChart) {
    depreciationChart.destroy();
  }

  const labels = curva.map(item => item.ano);
  const dataPrecos = curva.map(item => item.preco_medio);

  depreciationChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Preço Médio de Mercado (R$)',
          data: dataPrecos,
          borderColor: '#E11138',
          backgroundColor: 'rgba(225, 17, 56, 0.08)',
          borderWidth: 3,
          fill: true,
          tension: 0.3,
          pointBackgroundColor: labels.map(ano => ano === anoAtual ? '#059669' : '#E11138'),
          pointRadius: labels.map(ano => ano === anoAtual ? 7 : 4),
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: function(context) {
              return ` Preço Médio: R$ ${context.parsed.y.toLocaleString('pt-BR')}`;
            }
          }
        }
      },
      scales: {
        y: {
          ticks: {
            callback: value => `R$ ${(value / 1000).toFixed(0)}k`
          },
          grid: { color: '#F1F5F9' }
        },
        x: {
          grid: { display: false }
        }
      }
    }
  });
}

// ==========================================================================
// 4. EVENT LISTENERS E CONTROLES
// ==========================================================================
function initEventListeners() {
  // Modal de Configuração de Viagem & Origem
  const openTravelBtn = document.getElementById('openTravelConfigBtn');
  const travelModal = document.getElementById('travelModal');
  const closeTravelBtn = document.getElementById('travelModalCloseBtn');
  const cancelTravelBtn = document.getElementById('cancelTravelConfigBtn');
  const saveTravelBtn = document.getElementById('saveTravelConfigBtn');

  if (openTravelBtn && travelModal) {
    openTravelBtn.addEventListener('click', () => {
      document.getElementById('travelCityInput').value = state.travel.user_city;
      document.getElementById('travelUfSelect').value = state.travel.user_uf;
      document.getElementById('travelFuelSelect').value = state.travel.fuel_type;
      document.getElementById('travelFuelPriceInput').value = state.travel.fuel_price;
      document.getElementById('travelKmPerLInput').value = state.travel.km_per_liter;
      document.getElementById('travelTollInput').value = state.travel.toll_per_100km;
      document.getElementById('travelExtraInput').value = state.travel.extra_costs;
      travelModal.classList.add('open');
    });

    closeTravelBtn.addEventListener('click', () => travelModal.classList.remove('open'));
    cancelTravelBtn.addEventListener('click', () => travelModal.classList.remove('open'));
    travelModal.addEventListener('click', e => {
      if (e.target === travelModal) travelModal.classList.remove('open');
    });

    saveTravelBtn.addEventListener('click', () => {
      state.travel.user_city = document.getElementById('travelCityInput').value.trim() || 'São Paulo';
      state.travel.user_uf = document.getElementById('travelUfSelect').value;
      state.travel.fuel_type = document.getElementById('travelFuelSelect').value;
      state.travel.fuel_price = parseFloat(document.getElementById('travelFuelPriceInput').value) || 6.10;
      state.travel.km_per_liter = parseFloat(document.getElementById('travelKmPerLInput').value) || 12.0;
      state.travel.toll_per_100km = parseFloat(document.getElementById('travelTollInput').value) || 16.0;
      state.travel.extra_costs = parseFloat(document.getElementById('travelExtraInput').value) || 150.0;

      // Persistir no localStorage
      localStorage.setItem('wm_user_city', state.travel.user_city);
      localStorage.setItem('wm_user_uf', state.travel.user_uf);
      localStorage.setItem('wm_fuel_type', state.travel.fuel_type);
      localStorage.setItem('wm_fuel_price', state.travel.fuel_price);
      localStorage.setItem('wm_km_per_l', state.travel.km_per_liter);
      localStorage.setItem('wm_toll', state.travel.toll_per_100km);
      localStorage.setItem('wm_extra', state.travel.extra_costs);

      updateNavTravelSummary();
      travelModal.classList.remove('open');
      state.page = 1;
      fetchCars();
    });
  }

  // Input de Busca com Debounce
  const searchInput = document.getElementById('searchInput');
  searchInput.addEventListener('input', e => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      state.q = e.target.value;
      state.page = 1;
      fetchCars();
    }, 350);
  });

  document.getElementById('searchBtn').addEventListener('click', () => {
    state.q = searchInput.value;
    state.page = 1;
    fetchCars();
  });

  // Filtro de Inteligência de Preço (Radar)
  document.querySelectorAll('.wm-deal-option').forEach(el => {
    el.addEventListener('click', () => {
      document.querySelectorAll('.wm-deal-option').forEach(o => o.classList.remove('active'));
      el.classList.add('active');
      state.deal_type = el.getAttribute('data-deal');
      state.page = 1;
      fetchCars();
    });
  });

  // Tags Rápidas
  document.querySelectorAll('.wm-tag-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      if (pill.hasAttribute('data-deal')) {
        state.deal_type = pill.getAttribute('data-deal');
      } else if (pill.hasAttribute('data-price')) {
        state.preco_max = parseFloat(pill.getAttribute('data-price'));
        document.getElementById('priceRange').value = state.preco_max;
        updatePriceDisplay(state.preco_max);
      } else if (pill.hasAttribute('data-search')) {
        state.q = pill.getAttribute('data-search');
        document.getElementById('searchInput').value = state.q;
      } else if (pill.hasAttribute('data-km')) {
        state.km_max = parseFloat(pill.getAttribute('data-km'));
        document.getElementById('kmRange').value = state.km_max;
        document.getElementById('kmDisplay').innerText = `Até ${state.km_max.toLocaleString('pt-BR')} km`;
      }
      state.page = 1;
      fetchCars();
    });
  });

  // Filtro de UFs
  document.querySelectorAll('#ufPillGrid .wm-pill-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#ufPillGrid .wm-pill-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.uf = btn.getAttribute('data-uf');
      state.page = 1;
      fetchCars();
    });
  });

  // Filtro de Marca
  document.getElementById('brandSelect').addEventListener('change', e => {
    selectBrand(e.target.value);
  });

  // Filtro de Modelo
  document.getElementById('modelSelect').addEventListener('change', e => {
    selectModel(e.target.value);
  });

  // Range de Preço
  const priceRange = document.getElementById('priceRange');
  priceRange.addEventListener('input', e => {
    updatePriceDisplay(e.target.value);
  });
  priceRange.addEventListener('change', e => {
    state.preco_max = parseFloat(e.target.value);
    state.page = 1;
    fetchCars();
  });

  // Range de Quilometragem
  const kmRange = document.getElementById('kmRange');
  kmRange.addEventListener('input', e => {
    document.getElementById('kmDisplay').innerText = `Até ${parseFloat(e.target.value).toLocaleString('pt-BR')} km`;
  });
  kmRange.addEventListener('change', e => {
    state.km_max = parseFloat(e.target.value);
    state.page = 1;
    fetchCars();
  });

  // Ano De / Até
  document.getElementById('yearMinSelect').addEventListener('change', e => {
    state.ano_min = e.target.value;
    state.page = 1;
    fetchCars();
  });
  document.getElementById('yearMaxSelect').addEventListener('change', e => {
    state.ano_max = e.target.value;
    state.page = 1;
    fetchCars();
  });

  // Checkboxes de Tipo de Vendedor
  document.querySelectorAll('.seller-checkbox').forEach(cb => {
    cb.addEventListener('change', () => {
      const checked = Array.from(document.querySelectorAll('.seller-checkbox:checked')).map(c => c.value);
      state.tipo_vendedor = checked.length === 1 ? checked[0] : '';
      state.page = 1;
      fetchCars();
    });
  });

  // Ordenação
  document.getElementById('sortSelect').addEventListener('change', e => {
    state.sort = e.target.value;
    state.page = 1;
    fetchCars();
  });

  // Botão Limpar Filtros
  document.getElementById('resetFiltersBtn').addEventListener('click', resetFilters);

  // Fechar Modal
  document.getElementById('modalCloseBtn').addEventListener('click', () => {
    document.getElementById('carModal').classList.remove('open');
  });
  document.getElementById('carModal').addEventListener('click', e => {
    if (e.target === document.getElementById('carModal')) {
      document.getElementById('carModal').classList.remove('open');
    }
  });
}

function updatePriceDisplay(val) {
  document.getElementById('priceDisplay').innerText = parseFloat(val).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 });
}

function resetFilters() {
  state.q = '';
  state.uf = '';
  state.marca = '';
  state.modelo = '';
  state.ano_min = '';
  state.ano_max = '';
  state.preco_max = 600000;
  state.km_max = 200000;
  state.deal_type = '';
  state.tipo_vendedor = '';
  state.sort = 'deal_desc';
  state.page = 1;

  document.getElementById('searchInput').value = '';
  document.getElementById('brandSelect').value = '';
  document.getElementById('modelSelect').value = '';
  document.getElementById('modelSelect').disabled = true;
  document.getElementById('yearMinSelect').value = '';
  document.getElementById('yearMaxSelect').value = '';
  document.getElementById('priceRange').value = 600000;
  updatePriceDisplay(600000);
  document.getElementById('kmRange').value = 200000;
  document.getElementById('kmDisplay').innerText = 'Até 200.000 km';
  document.getElementById('sortSelect').value = 'deal_desc';

  document.querySelectorAll('#ufPillGrid .wm-pill-btn').forEach(b => b.classList.remove('active'));
  document.querySelector('#ufPillGrid .wm-pill-btn[data-uf=""]').classList.add('active');

  document.querySelectorAll('.wm-deal-option').forEach(o => o.classList.remove('active'));
  document.querySelector('.wm-deal-option[data-deal=""]').classList.add('active');

  document.querySelectorAll('.wm-brand-card-item').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.wm-sidebar-brand-btn').forEach(b => b.classList.remove('active'));
  const heroModelsBar = document.getElementById('heroModelsBar');
  if (heroModelsBar) heroModelsBar.classList.remove('visible');
  const heroChips = document.getElementById('heroModelsChips');
  if (heroChips) heroChips.innerHTML = '';
  const sidebarChips = document.getElementById('sidebarModelsChips');
  if (sidebarChips) sidebarChips.innerHTML = '';

  document.querySelectorAll('.seller-checkbox').forEach(c => c.checked = false);

  fetchCars();
}

function renderPagination(totalPages, currentPage) {
  const container = document.getElementById('pagination');
  if (totalPages <= 1) {
    container.innerHTML = '';
    return;
  }

  let html = `
    <button class="wm-page-btn" ${currentPage === 1 ? 'disabled' : ''} onclick="goToPage(${currentPage - 1})">
      <i class="fa-solid fa-chevron-left"></i> Anterior
    </button>
  `;

  for (let p = Math.max(1, currentPage - 2); p <= Math.min(totalPages, currentPage + 2); p++) {
    html += `
      <button class="wm-page-btn ${p === currentPage ? 'active' : ''}" onclick="goToPage(${p})">
        ${p}
      </button>
    `;
  }

  html += `
    <button class="wm-page-btn" ${currentPage === totalPages ? 'disabled' : ''} onclick="goToPage(${currentPage + 1})">
      Próxima <i class="fa-solid fa-chevron-right"></i>
    </button>
  `;

  container.innerHTML = html;
}

function goToPage(p) {
  state.page = p;
  fetchCars();
  window.scrollTo({ top: 400, behavior: 'smooth' });
}

function toggleFavorite(btn, event) {
  event.stopPropagation();
  const icon = btn.querySelector('i');
  if (icon.classList.contains('fa-regular')) {
    icon.classList.remove('fa-regular');
    icon.classList.add('fa-solid');
    icon.style.color = 'var(--wm-red)';
  } else {
    icon.classList.remove('fa-solid');
    icon.classList.add('fa-regular');
    icon.style.color = '#6B7280';
  }
}
