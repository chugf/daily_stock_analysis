import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import StockScreeningPage from '../StockScreeningPage';

const { enableAlphaSift, getAlphaSiftStatus, screenStocks } = vi.hoisted(() => ({
  enableAlphaSift: vi.fn(),
  getAlphaSiftStatus: vi.fn(),
  screenStocks: vi.fn(),
}));

vi.mock('../../api/alphasift', () => ({
  alphasiftApi: {
    enable: (...args: unknown[]) => enableAlphaSift(...args),
    getStatus: (...args: unknown[]) => getAlphaSiftStatus(...args),
    screen: (...args: unknown[]) => screenStocks(...args),
  },
}));

describe('StockScreeningPage', () => {
  beforeEach(() => {
    enableAlphaSift.mockReset();
    getAlphaSiftStatus.mockReset();
    screenStocks.mockReset();
  });

  it('re-syncs enabled state when AlphaSift install fails after config is enabled', async () => {
    getAlphaSiftStatus
      .mockResolvedValueOnce({
        enabled: false,
        available: false,
        installSpec: 'git+https://github.com/ZhuLinsen/alphasift.git',
      })
      .mockResolvedValueOnce({
        enabled: true,
        available: false,
        installSpec: 'git+https://github.com/ZhuLinsen/alphasift.git',
      });
    enableAlphaSift.mockRejectedValueOnce(new Error('安装 AlphaSift 失败'));

    render(<StockScreeningPage />);

    expect(await screen.findByText('选股未开启')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /运行选股/ })).toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: '开启 AlphaSift' }));

    await waitFor(() => expect(getAlphaSiftStatus).toHaveBeenCalledTimes(2));
    expect(screen.getByText('选股已开启')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /运行选股/ })).not.toBeDisabled();
    expect(screen.getByText('安装 AlphaSift 失败')).toBeInTheDocument();
  });
});
