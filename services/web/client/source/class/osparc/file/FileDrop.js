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

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.Canvas());

    const contentElement = this.getContentElement();
    contentElement.setStyles(this.self().getBorderStyle());
    const colorManager = qx.theme.manager.Color.getInstance();
    colorManager.addListener("changeTheme", () => contentElement.setStyles(this.self().getBorderStyle()));

    this._createChildControlImpl("drop-here");
    this._createChildControlImpl("svg-layer");

    this.addListenerOnce("appear", () => {
      // listen to drop files from local-system
      const domEl = this.getContentElement().getDomElement();
      [
        "dragenter",
        "dragover",
        "dragleave"
      ].forEach(signalName => {
        domEl.addEventListener(signalName, e => {
          const dragging = signalName !== "dragleave";
          this.__draggingFile(e, dragging);
        }, this);
      });
      domEl.addEventListener("drop", this.__dropFile.bind(this), false);

      this.setDroppable(true);
      [
        "dragover",
        "dragleave"
      ].forEach(signalName => {
        this.addListener(signalName, e => {
          console.log(signalName);
          const dragging = signalName !== "dragleave";
          if (dragging === false) {
            this.__dragging = dragging;
          }
          this.__draggingLink(e, dragging);
        }, this);
      });
      this.addListener("mousemove", e => {
        console.log("mousemove", this.__dragging);
        if (this.__dragging) {
          this.__draggingLink(e, true);
        }
      }, this);
      /*
      this.addListener("mouseup", e => {
        console.log("mouseup", this.__dragging);
        if (this.__dragging) {
          this.__dropLink(e, true);
        }
      }, this);
      this.addListener("drop", this.__dropLink.bind(this), false);
      */
    });
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
    "uploadFile": "qx.event.type.Data",
    "setOutputFile": "qx.event.type.Data"
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

    resetDropAction: function() {
      this.getChildControl("drop-here").show();
      this.getChildControl("drop-me").exclude();
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

    __allowDragFile: function(e) {
      let allow = false;
      if (this.__dragging) {
        // item still being dragged
        allow = true;
      } else {
        allow = e.target instanceof SVGElement;
        this.__dragging = allow;
      }
      return allow;
    },

    __allowDragLink: function(e) {
      let allow = false;
      if (this.__dragging) {
        // item still being dragged
        allow = true;
      } else if ("supportsType" in e) {
        // item drag from osparc's file tree
        allow = e.supportsType("osparc-file-link");
        this.__dragging = allow;
      }
      return allow;
    },

    __draggingFile: function(e, dragging) {
      if (this.__allowDragFile(e)) {
        e.preventDefault();
        e.stopPropagation();
      } else {
        dragging = false;
      }

      let posX = e.offsetX + 2;
      let posY = e.offsetY + 2;
      const dropHere = this.getChildControl("drop-here");
      const dropHint = this.getChildControl("drop-me");
      if (dragging && "rect" in dropHint) {
        dropHere.exclude();
        dropHint.show();
        dropHint.setLayoutProperties({
          left: posX,
          top: posY
        });
        osparc.component.workbench.SvgWidget.updateRect(dropHint.rect, posX, posY);
      } else {
        dropHere.show();
        dropHint.exclude();
      }
    },

    __draggingLink: function(e, dragging) {
      if (this.__allowDragLink(e)) {
        e.preventDefault();
        e.stopPropagation();
      } else {
        dragging = false;
      }

      const pos = this.__pointerEventToScreenPos(e);
      const posX = pos.x;
      const posY = pos.y;
      const dropHere = this.getChildControl("drop-here");
      const dropHint = this.getChildControl("drop-me");
      if (dragging && "rect" in dropHint) {
        dropHere.exclude();
        dropHint.show();
        dropHint.setLayoutProperties({
          left: posX,
          top: posY
        });
        osparc.component.workbench.SvgWidget.updateRect(dropHint.rect, posX, posY);
      } else {
        dropHere.show();
        dropHint.exclude();
      }
    },

    __dropFile: function(e) {
      this.__draggingFile(e, false);

      if ("dataTransfer" in e) {
        this.__dragging = false;
        const files = e.dataTransfer.files;
        if (files.length === 1) {
          const fileList = e.dataTransfer.files;
          if (fileList.length) {
            this.fireDataEvent("uploadFile", files);
          }
        } else {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Only one file is accepted"), "ERROR");
        }
      }
    },

    __dropLink: function(e) {
      this.__draggingLink(e, false);

      if ("supportsType" in e && e.supportsType("osparc-file-link")) {
        this.__dragging = false;
        const data = e.getData("osparc-file-link")["dragData"];
        this.fireDataEvent("setOutputFile", data);
      }
    }
  }
});
