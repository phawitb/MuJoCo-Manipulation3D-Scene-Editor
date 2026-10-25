/** At most one request in flight; unsent mouse events collapse to the newest pose. */
export class LatestTarget {
  private pending: number[] | null = null;
  private timer: ReturnType<typeof setTimeout> | undefined;
  private active: Promise<void> | null = null;
  private disposed = false;
  constructor(
    private send: (q: number[]) => Promise<unknown>,
    private fail: (e: unknown) => void,
  ) {}
  push(q: number[]) {
    if (this.disposed) return;
    this.pending = [...q];
    this.schedule();
  }
  private schedule() {
    if (this.active || this.timer || !this.pending || this.disposed) return;
    this.timer = setTimeout(() => {
      this.timer = undefined;
      const q = this.pending!;
      this.pending = null;
      this.active = this.send(q)
        .then(
          () => {},
          (e) => {
            this.pending = null;
            if (!this.disposed) this.fail(e);
          },
        )
        .finally(() => {
          this.active = null;
          this.schedule();
        });
    }, 35);
  }
  async cancel() {
    this.pending = null;
    clearTimeout(this.timer);
    this.timer = undefined;
    await this.active;
  }
  dispose() {
    this.disposed = true;
    void this.cancel();
  }
}
