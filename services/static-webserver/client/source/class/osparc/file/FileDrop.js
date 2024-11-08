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

    let msg = "<center>";
    const options = [
      this.tr("Upload file"),
      this.tr("Drop file from explorer"),
      this.tr("Drop file from tree"),
      this.tr("Provide Link")
    ];
    for (let i=0; i<options.length; i++) {
      msg += options[i];
      if (i < options.length-1) {
        msg += "<br>" + this.tr("or") + "<br>";
      }
    }
    msg += "</center>";

    const dropHereMessage = this.__dropHereMessage = new qx.ui.basic.Label(msg).set({
      font: "text-14",
      rich: true,
      alignX: "center",
      alignY: "middle"
    });
    this._add(dropHereMessage);

    dropHereMessage.addListener("appear", () => this.__centerDropHereMessage(), this);
    this.addListener("resize", () => this.__centerDropHereMessage(), this);

    const svgLayer = this.__svgLayer = new osparc.workbench.SvgWidget();
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
        "border-radius": "10px",
        "border-color": qx.theme.manager.Color.getInstance().resolve("background-main-4"),
        "border-style": "dotted"
      };
    },

    getNoBorderStyle: function() {
      return {
        "border-width": "0px"
      };
    },

    getFilesFromEvent: function(e) {
      const files = [];
      if (e.dataTransfer.items) {
        const items = e.dataTransfer.items;
        for (let i = 0; i < items.length; i++) {
          // If dropped items aren't files, reject them
          if (items[i].webkitGetAsEntry()["isFile"]) {
            const file = items[i].getAsFile();
            files.push(file);
          }
        }
      }
      return files;
    },

    ONE_FILE_ONLY: qx.locale.Manager.tr("Only one file at a time is accepted.") + "<br>" + qx.locale.Manager.tr("Please zip all files together."),
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
    __dropHereMessage: null,
    __dropMe: null,
    __isDraggingFile: null,
    __isDraggingLink: null,

    __applyShowBorder: function(show) {
      const contentElement = this.getContentElement();
      contentElement.setStyles(show ? this.self().getBorderStyle() : this.self().getNoBorderStyle());
    },

    __applyShowDropHere: function(value) {
      this.__dropHereMessage.setVisibility(value ? "visible" : "excluded");
    },

    __centerDropHereMessage: function() {
      const dropHere = this.__dropHereMessage;
      // center it
      const dropHereBounds = dropHere.getBounds() || dropHere.getSizeHint();
      const fileDropBounds = this.getBounds() || this.getSizeHint();
      dropHere.setLayoutProperties({
        top: parseInt((fileDropBounds.height - dropHereBounds.height) / 2),
        left: parseInt((fileDropBounds.width - dropHereBounds.width) / 2)
      });
    },

    setDropHereMessage: function(msg) {
      this.__dropHereMessage.set({
        value: msg
      });
      this.__centerDropHereMessage();
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
        this.__dropHereMessage.exclude();
        this.__updateDropMe(posX, posY);
      } else {
        if (this.getShowDropHere()) {
          this.__dropHereMessage.show();
        }
        this.__hideDropMe();
      }
    },

    __updateDropMe: function(posX, posY) {
      const boxWidth = 120;
      const boxHeight = 60;
      if (this.__dropMe === null) {
        this.__dropMe = new qx.ui.basic.Label(this.tr("Drop me")).set({
          font: "text-14",
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
        osparc.wrapper.Svg.updateItemPos(dropMe.rect, posX - boxWidth, posY - boxHeight);
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
        const files = osparc.file.FileDrop.getFilesFromEvent(e);
        if (files.length) {
          if (files.length === 1) {
            this.fireDataEvent("localFileDropped", {
              data: files,
              pos: this.__pointerFileEventToScreenPos(e)
            });
          } else {
            osparc.FlashMessenger.getInstance().logAs(osparc.file.FileDrop.ONE_FILE_ONLY, "ERROR");
          }
        } else {
          osparc.FlashMessenger.getInstance().logAs(this.tr("Folders are not accepted. You might want to upload a zip file."), "ERROR");
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
