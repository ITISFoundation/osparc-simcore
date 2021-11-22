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

/**
 * @ignore(SVGElement)
 */

qx.Class.define("osparc.file.FileDrop", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.Canvas());

    const contentElement = this.getContentElement();
    contentElement.setStyles(this.self().getBorderStyle());
    const colorManager = qx.theme.manager.Color.getInstance();
    colorManager.addListener("changeTheme", () => {
      if (this.getShowBorder()) {
        contentElement.setStyles(this.self().getBorderStyle());
      }
    }, this);
    this._createChildControlImpl("drop-here");
    this._createChildControlImpl("svg-layer");

    this.addListenerOnce("appear", () => {
      // listen to drag&drop files from local-storage
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

      // listen to drag&drop file-links from osparc-storage
      this.setDroppable(true);

      const stopDraggingLink = () => {
        this.__isDraggingLink = null;
        this.__updateWidgets(false);
      };
      const startDraggingLink = e => {
        this.addListenerOnce("dragleave", stopDraggingLink, this);
        this.addListenerOnce("dragover", startDraggingLink, this);
        this.__draggingLink(e, true);
      };
      this.addListenerOnce("dragover", startDraggingLink, this);

      this.addListener("mousemove", e => {
        if (this.__isDraggingLink) {
          this.__draggingLink(e, true);
        }
      }, this);
      this.addListener("mouseup", e => {
        if (this.__isDraggingLink) {
          this.__dropLink(e, true);
        }
      }, this);
    }, this);
  },

  statics: {
    getBorderStyle: function() {
      return {
        "border-radius": "20px",
        "border-color": qx.theme.manager.Color.getInstance().resolve("contrasted-background+"),
        "border-style": "dotted"
      };
    },

    getNoBorderStyle: function() {
      return {
        "border-radius": "0px"
      };
    }
  },

  events: {
    "uploadFile": "qx.event.type.Data",
    "setOutputFile": "qx.event.type.Data"
  },

  properties: {
    showBorder: {
      check: "Boolean",
      init: true,
      apply: "__applyShowBorder"
    }
  },

  members: {
    __isDraggingFile: null,
    __isDraggingLink: null,

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
            top: 40,
            left: 40
          });
          control.addListener("appear", () => {
            // center it
            const hintBounds = control.getBounds() || control.getSizeHint();
            const {
              height,
              width
            } = this.getBounds();
            control.setLayoutProperties({
              top: Math.round((height - hintBounds.height) / 2),
              left: Math.round((width - hintBounds.width) / 2)
            });
          }, this);
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
          if (svgLayer.getReady()) {
            control.rect = svgLayer.drawDashedRect(120, 60);
          } else {
            svgLayer.addListenerOnce("SvgWidgetReady", () => control.rect = svgLayer.drawDashedRect(120, 60), this);
          }
        }
      }
      return control || this.base(arguments, id);
    },

    __applyShowBorder: function(show) {
      const contentElement = this.getContentElement();
      contentElement.setStyles(show ? this.self().getBorderStyle() : this.self().getNoBorderStyle());
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
      if (this.__isDraggingFile) {
        // item still being dragged
        allow = true;
      } else {
        allow = e.target instanceof SVGElement;
        this.__isDraggingFile = allow;
      }
      return allow;
    },

    __allowDragLink: function(e) {
      let allow = false;
      if (this.__isDraggingLink) {
        // item still being dragged
        allow = true;
      } else if ("supportsType" in e) {
        // item drag from osparc's file tree
        allow = e.supportsType("osparc-file-link");
        if (allow) {
          // store "osparc-file-link" data in variable,
          // because the mousemove event doesn't contain that information
          this.__isDraggingLink = e.getData("osparc-file-link");
        }
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

      const posX = e.offsetX + 2;
      const posY = e.offsetY + 2;
      this.__updateWidgets(dragging, posX, posY);
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
      this.__updateWidgets(dragging, posX, posY);
    },

    __updateWidgets: function(dragging, posX, posY) {
      this.getChildControl("drop-here").set({
        visibility: dragging ? "excluded" : "visible"
      });
      const dropMe = this.getChildControl("drop-me").set({
        visibility: dragging ? "visible" : "excluded"
      });
      if ("rect" in dropMe) {
        if (dragging) {
          if (dropMe.rect.style.display === "none") {
            dropMe.rect.style.display = "block";
          }
          dropMe.setLayoutProperties({
            left: posX,
            top: posY
          });
          osparc.component.workbench.SvgWidget.updateRect(dropMe.rect, posX, posY);
        } else {
          dropMe.rect.style.display = "none";
        }
      }
    },

    __dropFile: function(e) {
      this.__draggingFile(e, false);

      this.__isDraggingFile = false;
      if ("dataTransfer" in e) {
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

      if (this.__isDraggingLink && "dragData" in this.__isDraggingLink) {
        this.fireDataEvent("setOutputFile", this.__isDraggingLink["dragData"]);
        this.__isDraggingLink = null;
      }
    }
  }
});
