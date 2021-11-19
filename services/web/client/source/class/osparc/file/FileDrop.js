/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.file.FileDrop", {
  extend: qx.ui.core.Widget,

  construct: function(node) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.Canvas());

    if (node) {
      this.setNode(node);
    }

    this.addListenerOnce("appear", () => {
      const domEl = this.getContentElement().getDomElement();
      [
        "dragenter",
        "dragover",
        "dragleave"
      ].forEach(signalName => {
        domEl.addEventListener(signalName, e => {
          const dragging = signalName !== "dragleave";
          this.__dragging(e, dragging);
        }, this);
      });
      domEl.addEventListener("drop", e => this.__drop(e), this);

      this.setDroppable(true);
      [
        "dragenter",
        "dragover", // on target (pointer over)
        "dragleave" // on target (pointer out)
      ].forEach(signalName => {
        this.addListener(signalName, e => {
          const dragging = signalName !== "dragleave";
          if (dragging === false) {
            this.__draggingFile = dragging;
          }
          this.__dragging(e, dragging);
        }, this);
      });
      [
        "mousemove"
      ].forEach(signalName => {
        this.addListener(signalName, e => {
          if (this.__draggingFile) {
            this.__dragging(e, true);
          }
        }, this);
      });
      this.addListener("drop", e => this.__drop(e), this);
    });

    const contentElement = this.getContentElement();
    contentElement.setStyles(this.self().getBorderStyle());
    const colorManager = qx.theme.manager.Color.getInstance();
    colorManager.addListener("changeTheme", () => contentElement.setStyles(this.self().getBorderStyle()));

    this._createChildControlImpl("drop-here");
    this._createChildControlImpl("svg-layer");
  },

  statics: {
    getBorderStyle: function() {
      return {
        "border-radius": "20px",
        "border-color": qx.theme.manager.Color.getInstance().resolve("contrasted-background+"),
        "border-style": "dotted"
      };
    }
  },

  events: {
    "uploadFile": "qx.event.type.Data"
  },

  properties: {
    node: {
      check: "osparc.data.model.Node"
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control = null;
      switch (id) {
        case "drop-here":
          control = new qx.ui.basic.Label(this.tr("Drop here")).set({
            font: "title-14",
            alignX: "center",
            alignY: "middle"
          });
          this._add(control, {
            top: 20,
            left: 30
          });
          break;
        case "svg-layer":
          control = new osparc.component.workbench.SvgWidget();
          this._add(control, {
            top: 0,
            right: 0,
            bottom: 0,
            left: 0
          });
          break;
        case "drop-me": {
          control = new qx.ui.basic.Label(this.tr("Drop me")).set({
            font: "title-14",
            textAlign: "center"
          });
          this._add(control);
          const svgLayer = this.getChildControl("svg-layer");
          control.rect = svgLayer.drawDashedRect(120, 60);
        }
      }
      return control || this.base(arguments, id);
    },

    __pointerEventToScreenPos: function(e) {
      const rect = e.getCurrentTarget()
        .getContentElement().getDomElement()
        .getBoundingClientRect();
      return {
        x: e.getDocumentLeft() - rect.x,
        y: e.getDocumentTop() - rect.y
      };
    },

    __allowDrag: function(e) {
      let allow = false;
      if (this.__draggingFile) {
        // item still being dragged
        allow = true;
      } else if ("supportsType" in e) {
        // item drag from osparc's file tree
        allow = e.supportsType("osparc-file-link");
        this.__draggingFile = allow;
      } else {
        // item drag from the outside world
        allow = e.target instanceof SVGElement;
        this.__draggingFile = allow;
      }
      return allow;
    },

    __dragging: function(e, dragging) {
      if (this.__allowDrag(e)) {
        e.preventDefault();
        e.stopPropagation();
      } else {
        dragging = false;
      }

      let posX = 0;
      let posY = 0;
      if ("offsetX" in e && "offsetY" in e) {
        posX = e.offsetX + 2;
        posY = e.offsetY + 2;
      } else {
        const pos = this.__pointerEventToScreenPos(e);
        posX = pos.x;
        posY = pos.y;
      }

      const dropHint = this.getChildControl("drop-me");
      if (dragging && "rect" in dropHint) {
        dropHint.show();
        dropHint.setLayoutProperties({
          left: posX,
          top: posY
        });
        osparc.component.workbench.SvgWidget.updateRect(dropHint.rect, posX, posY);
      } else {
        dropHint.exclude();
      }
    },

    __drop: function(e) {
      this.__dragging(e, false);

      if ("dataTransfer" in e) {
        this.__draggingFile = false;
        const files = e.dataTransfer.files;
        if (files.length === 1) {
          const fileList = e.dataTransfer.files;
          if (fileList.length) {
            this.fireDataEvent("uploadFile", files[0]);
          }
        } else {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Only one file is accepted"), "ERROR");
        }
      } else if ("supportsType" in e && e.supportsType("osparc-file-link")) {
        this.__draggingFile = false;
        const data = e.getData("osparc-file-link")["dragData"];
        if (this.getNode()) {
          osparc.file.FilePicker.setOutputValueFromStore(this.getNode(), data.getLocation(), data.getDatasetId(), data.getFileId(), data.getLabel());
        }
      }
    }
  }
});
