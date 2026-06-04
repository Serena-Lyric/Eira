// @ts-nocheck
/**
 * Copyright(c) Live2D Inc. All rights reserved.
 *
 * Use of this source code is governed by the Live2D Open Software license
 * that can be found at https://www.live2d.com/eula/live2d-open-software-license-agreement_en.html.
 *
 * ── Eira 改造 ────────────────────────────────────────────────
 * 官方サンプルは複数 canvas を document.body に生成し、document 全体に
 * ポインタイベントを張る。Eira では Vue が用意した 1 枚の canvas を受け取り、
 * イベントもその canvas にのみ束縛する（グローバル汚染を避ける）。
 */

import { CubismFramework, Option } from '@framework/live2dcubismframework';
import * as LAppDefine from './lappdefine';
import { LAppPal } from './lapppal';
import { LAppSubdelegate } from './lappsubdelegate';
import { CubismLogError } from '@framework/utils/cubismdebug';

export let s_instance: LAppDelegate = null;

/**
 * アプリケーションクラス。Cubism SDK の管理を行う。
 */
export class LAppDelegate {
  public static getInstance(): LAppDelegate {
    if (s_instance == null) {
      s_instance = new LAppDelegate();
    }
    return s_instance;
  }

  public static releaseInstance(): void {
    if (s_instance != null) {
      s_instance.release();
    }
    s_instance = null;
  }

  private onPointerBegan(e: PointerEvent): void {
    this._subdelegate?.onPointBegan(e.pageX, e.pageY);
  }

  private onPointerMoved(e: PointerEvent): void {
    this._subdelegate?.onPointMoved(e.pageX, e.pageY);
  }

  private onPointerEnded(e: PointerEvent): void {
    this._subdelegate?.onPointEnded(e.pageX, e.pageY);
  }

  private onPointerCancel(e: PointerEvent): void {
    this._subdelegate?.onTouchCancel(e.pageX, e.pageY);
  }

  public onResize(): void {
    this._subdelegate?.onResize();
  }

  /**
   * メインループ。requestAnimationFrame で回す。
   */
  public run(): void {
    const loop = (): void => {
      if (s_instance == null) {
        return;
      }
      LAppPal.updateTime();
      this._subdelegate?.update();
      this._animationFrameId = requestAnimationFrame(loop);
    };
    loop();
  }

  /**
   * 解放する。
   */
  public release(): void {
    if (this._animationFrameId != null) {
      cancelAnimationFrame(this._animationFrameId);
      this._animationFrameId = null;
    }
    this.releaseEventListener();
    this.releaseSubdelegate();

    CubismFramework.dispose();
    this._cubismOption = null;
  }

  private releaseEventListener(): void {
    if (!this._canvas) {
      return;
    }
    this._canvas.removeEventListener('pointerdown', this.pointBeganEventListener);
    this._canvas.removeEventListener('pointermove', this.pointMovedEventListener);
    this._canvas.removeEventListener('pointerup', this.pointEndedEventListener);
    this._canvas.removeEventListener('pointercancel', this.pointCancelEventListener);
    this.pointBeganEventListener = null;
    this.pointMovedEventListener = null;
    this.pointEndedEventListener = null;
    this.pointCancelEventListener = null;
  }

  private releaseSubdelegate(): void {
    this._subdelegate?.release();
    this._subdelegate = null;
  }

  /**
   * APP に必要な物を初期化する。
   * @param canvas Vue 側で生成・配置済みの canvas
   */
  public initialize(canvas: HTMLCanvasElement): boolean {
    this._canvas = canvas;
    this.initializeCubism();

    this._subdelegate = new LAppSubdelegate();
    this._subdelegate.initialize(canvas);

    if (this._subdelegate.isContextLost()) {
      CubismLogError(
        'The WebGL context was lost, possibly because the acquisition limit for WebGLRenderingContext was reached.'
      );
      return false;
    }

    this.initializeEventListener();
    return true;
  }

  private initializeEventListener(): void {
    this.pointBeganEventListener = this.onPointerBegan.bind(this);
    this.pointMovedEventListener = this.onPointerMoved.bind(this);
    this.pointEndedEventListener = this.onPointerEnded.bind(this);
    this.pointCancelEventListener = this.onPointerCancel.bind(this);

    const opt = { passive: true };
    this._canvas.addEventListener('pointerdown', this.pointBeganEventListener, opt);
    this._canvas.addEventListener('pointermove', this.pointMovedEventListener, opt);
    this._canvas.addEventListener('pointerup', this.pointEndedEventListener, opt);
    this._canvas.addEventListener('pointercancel', this.pointCancelEventListener, opt);
  }

  private initializeCubism(): void {
    LAppPal.updateTime();

    this._cubismOption.logFunction = LAppPal.printMessage;
    this._cubismOption.loggingLevel = LAppDefine.CubismLoggingLevel;
    CubismFramework.startUp(this._cubismOption);
    CubismFramework.initialize();
  }

  public getSubdelegate(): LAppSubdelegate {
    return this._subdelegate;
  }

  private constructor() {
    this._cubismOption = new Option();
    this._subdelegate = null;
    this._canvas = null;
    this._animationFrameId = null;
  }

  private _cubismOption: Option;
  private _canvas: HTMLCanvasElement;
  private _subdelegate: LAppSubdelegate;
  private _animationFrameId: number | null;

  private pointBeganEventListener: (ev: PointerEvent) => void;
  private pointMovedEventListener: (ev: PointerEvent) => void;
  private pointEndedEventListener: (ev: PointerEvent) => void;
  private pointCancelEventListener: (ev: PointerEvent) => void;
}
