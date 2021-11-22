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

    const dropHere = this.__dropHere = new qx.ui.basic.Label(this.tr("Drop file here")).set({
      font: "title-14",
      alignX: "center",
      alignY: "middle"
    });
    this._add(dropHere, {
      top: 40,
      left: 40
    });
    dropHere.addListener("appear", () => {
      // center it
      const dropHereBounds = dropHere.getBounds() || dropHere.getSizeHint();
      const {
        height,
        width
      } = this.getBounds();
      dropHere.setLayoutProperties({
        top: parseInt((height - dropHereBounds.height) / 2),
        left: parseInt((width - dropHereBounds.width) / 2)
      });
    }, this);

    const svgLayer = this.__svgLayer = new osparc.component.workbench.SvgWidget();
    this._add(svgLayer, {
      top: 0,
      right: 0,
      bottom: 0,
      left: 0
    });

    this.__addDragAndDropListeners();
  },

  statics: {
    getBorderStyle: function() {
      return {
        "border-width": "3px",
        "border-radius": "20px",
        "border-color": qx.theme.manager.Color.getInstance().resolve("contrasted-background+"),
        "border-style": "dotted"
      };
    },

    getNoBorderStyle: function() {
      return {
        "border-width": "0px"
      };
    }
  },

  events: {
    "localFileDropped": "qx.event.type.Data",
    "fileLinkDropped": "qx.event.type.Data"
  },

  properties: {
    showBorder: {
      check: "Boolean",
      init: true,
      apply: "__applyShowBorder"
    },

    showDropHere: {
      check: "Boolean",
      init: true,
      apply: "__applyShowDropHere"
    }
  },

  members: {
    __svgLayer: null,
    __dropHere: null,
    __dropMe: null,
    __isDraggingFile: null,
    __isDraggingLink: null,

    __applyShowBorder: function(show) {
      const contentElement = this.getContentElement();
      contentElement.setStyles(show ? this.self().getBorderStyle() : this.self().getNoBorderStyle());
    },

    __applyShowDropHere: function(value) {
      this.__dropHere.setVisibility(value ? "visible" : "excluded");
    },

    resetDropAction: function() {
      this.__updateWidgets(false);
    },

    __pointerFileEventToScreenPos: function(e) {
      const rect = this.getContentElement().getDomElement().getBoundingClientRect();
      return {
        x: e.pageX - rect.x,
        y: e.pageY - rect.y
      };
    },

    __pointerLinkEventToScreenPos: function(e) {
      const rect = this.getContentElement().getDomElement().getBoundingClientRect();
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

      const pos = this.__pointerFileEventToScreenPos(e);
      this.__updateWidgets(dragging, pos.x, pos.y);
    },

    __draggingLink: function(e, dragging) {
      if (this.__allowDragLink(e)) {
        e.preventDefault();
        e.stopPropagation();
      } else {
        dragging = false;
      }

      const pos = this.__pointerLinkEventToScreenPos(e);
      this.__updateWidgets(dragging, pos.x, pos.y);
    },

    __updateWidgets: function(dragging, posX, posY) {
      if (dragging) {
        this.__dropHere.exclude();
        this.__updateDropMe(posX, posY);
      } else {
        if (this.getShowDropHere()) {
          this.__dropHere.show();
        }
        this.__hideDropMe();
      }
    },

    __updateDropMe: function(posX, posY) {
      const boxWidth = 120;
      const boxHeight = 60;
      if (this.__dropMe === null) {
        this.__dropMe = new qx.ui.basic.Label(this.tr("Drop me")).set({
          font: "title-14",
          textAlign: "center"
        });
        this._add(this.__dropMe);
        const svgLayer = this.__svgLayer;
        if (svgLayer.getReady()) {
          this.__dropMe.rect = svgLayer.drawDashedRect(boxWidth, boxHeight);
        } else {
          svgLayer.addListenerOnce("SvgWidgetReady", () => this.__dropMe.rect = svgLayer.drawDashedRect(boxWidth, boxHeight), this);
        }
      }
      const dropMe = this.__dropMe;
      dropMe.show();
      const dropMeBounds = dropMe.getBounds() || dropMe.getSizeHint();
      dropMe.setLayoutProperties({
        left: posX - parseInt(dropMeBounds.width/2) - parseInt(boxWidth/2),
        top: posY - parseInt(dropMeBounds.height/2)- parseInt(boxHeight/2)
      });
      if ("rect" in dropMe) {
        dropMe.rect.stroke({
          width: 1
        });
        osparc.component.workbench.SvgWidget.updateRect(dropMe.rect, posX - boxWidth, posY - boxHeight);
      }
    },

    __hideDropMe: function() {
      const dropMe = this.__dropMe;
      if (dropMe) {
        if ("rect" in dropMe) {
          dropMe.rect.stroke({
            width: 0
          });
        }
        dropMe.exclude();
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
            this.fireDataEvent("localFileDropped", {
              data: files,
              pos: this.__pointerFileEventToScreenPos(e)
            });
          }
        } else {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Only one file is accepted"), "ERROR");
        }
      }
    },

    __dropLink: function(e) {
      this.__draggingLink(e, false);

      if (this.__isDraggingLink && "dragData" in this.__isDraggingLink) {
        this.fireDataEvent("fileLinkDropped", {
          data: this.__isDraggingLink["dragData"],
          pos: this.__pointerLinkEventToScreenPos(e)
        });
        this.__isDraggingLink = null;
      }
    },

    __addDragAndDropListeners: function() {
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
    }
  }
});
