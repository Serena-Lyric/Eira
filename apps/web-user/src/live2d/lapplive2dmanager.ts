// @ts-nocheck
/**
 * Copyright(c) Live2D Inc. All rights reserved.
 *
 * Use of this source code is governed by the Live2D Open Software license
 * that can be found at https://www.live2d.com/eula/live2d-open-software-license-agreement_en.html.
 *
 * ── Eira 改造 ────────────────────────────────────────────────
 * 官方サンプルの多シーン切り替え（ModelDir/nextScene/changeScene）を撤去し、
 * 単一モデルを loadModel(dir, fileName) で明示的に読み込む方式に変更。
 */

import { CubismMatrix44 } from '@framework/math/cubismmatrix44';
import { ACubismMotion } from '@framework/motion/acubismmotion';
import { CubismWebGLOffscreenManager } from '@framework/rendering/cubismoffscreenmanager';

import * as LAppDefine from './lappdefine';
import { LAppModel } from './lappmodel';
import { LAppPal } from './lapppal';
import { LAppSubdelegate } from './lappsubdelegate';

/**
 * CubismModel を管理するクラス（単一モデル）。
 */
export class LAppLive2DManager {
  private releaseAllModel(): void {
    this._models.length = 0;
  }

  public setOffscreenSize(width: number, height: number): void {
    this._offscreenSize = { w: width, h: height };
    for (let i = 0; i < this._models.length; i++) {
      const model: LAppModel = this._models[i];
      model?.setRenderTargetSize(width, height);
    }
  }

  public onDrag(x: number, y: number): void {
    // Eira: 拖拽用于平移视图（控制器侧处理），此处不做头部朝向跟随，避免冲突。
  }

  public onTap(x: number, y: number): void {
    const model: LAppModel = this._models[0];
    if (!model) {
      return;
    }

    if (model.hitTest(LAppDefine.HitAreaNameHead, x, y)) {
      model.setRandomExpression();
    } else if (model.hitTest(LAppDefine.HitAreaNameBody, x, y)) {
      model.startRandomMotion(
        LAppDefine.MotionGroupTapBody,
        LAppDefine.PriorityNormal,
        this.finishedMotion,
        this.beganMotion
      );
    }
  }

  /**
   * 画面更新。モデルの更新・描画を行う。
   * モデル読み込み完了前は描画しない（renderOrders 未初期化での崩壊回避）。
   */
  public onUpdate(): void {
    const model: LAppModel = this._models[0];
    if (!model || !model.getModel()) {
      return;
    }

    const gl = this._subdelegate.getGl();
    CubismWebGLOffscreenManager.getInstance().beginFrameProcess(gl);

    const { width, height } = this._subdelegate.getCanvas();
    const projection: CubismMatrix44 = new CubismMatrix44();

    if (model.getModel().getCanvasWidth() > 1.0 && width < height) {
      model.getModelMatrix().setWidth(2.0);
      projection.scale(1.0, width / height);
    } else {
      projection.scale(height / width, 1.0);
    }

    if (this._viewMatrix != null) {
      projection.multiplyByMatrix(this._viewMatrix);
    }

    model.update();
    model.draw(projection); // 参照渡しなので projection は変質する。

    CubismWebGLOffscreenManager.getInstance().endFrameProcess(gl);
    CubismWebGLOffscreenManager.getInstance().releaseStaleRenderTextures(gl);
  }

  /**
   * モデルを読み込む。
   * @param dir model3.json があるディレクトリ（末尾スラッシュ付き、例: /live2d/mao_pro_zh/runtime/）
   * @param fileName model3.json のファイル名
   */
  public loadModel(dir: string, fileName: string): LAppModel {
    if (LAppDefine.DebugLogEnable) {
      LAppPal.printMessage(`[Live2D] loadModel: ${dir}${fileName}`);
    }
    this.releaseAllModel();
    const instance = new LAppModel();
    instance.setSubdelegate(this._subdelegate);
    instance.loadAssets(dir, fileName);
    this._models.push(instance);
    if (this._offscreenSize) {
      instance.setRenderTargetSize(this._offscreenSize.w, this._offscreenSize.h);
    }
    return instance;
  }

  public getModel(): LAppModel {
    return this._models[0];
  }

  public setViewMatrix(m: CubismMatrix44) {
    for (let i = 0; i < 16; i++) {
      this._viewMatrix.getArray()[i] = m.getArray()[i];
    }
  }

  public constructor() {
    this._subdelegate = null;
    this._viewMatrix = new CubismMatrix44();
    this._models = new Array<LAppModel>();
    this._offscreenSize = null;
  }

  public release(): void {
    this.releaseAllModel();
  }

  /**
   * 初期化。官方と異なりここではモデルを読み込まない（loadModel で明示）。
   */
  public initialize(subdelegate: LAppSubdelegate): void {
    this._subdelegate = subdelegate;
  }

  private _subdelegate: LAppSubdelegate;
  private _offscreenSize: { w: number; h: number } | null;

  _viewMatrix: CubismMatrix44;
  _models: Array<LAppModel>;

  beganMotion = (self: ACubismMotion): void => {};
  finishedMotion = (self: ACubismMotion): void => {};
}
