import { LineChart } from 'lucide-react';
import { defineAppModule } from '@/lib/module-core';

export default defineAppModule({
  id: 'market',
  name: 'Market',
  labelKey: 'nav.market',
  icon: LineChart,
  description: 'Reference market data — gold board, stocks, finance',
  basePath: '/market',
  displayOrder: 40,
  navigation: [
    { id: 'market-gold', type: 'link', labelKey: 'nav.gold', path: '/market/gold' },
    { id: 'market-stocks', type: 'link', labelKey: 'nav.stock', path: '/market/stocks' },
    { id: 'market-finance', type: 'link', labelKey: 'nav.finance', path: '/market/finance' },
  ],
});
