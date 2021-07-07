/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Window that is used to represent a node in the WorkbenchUI.
 *
 * It implements Drag&Drop mechanism to provide internode connections.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let nodeUI = new osparc.component.workbench.NodeUI(node);
 *   nodeUI.populateNodeLayout();
 *   workbench.add(nodeUI)
 * </pre>
 */

qx.Class.define("osparc.component.workbench.NodeUI", {
  extend: osparc.component.workbench.BaseNodeUI,

  /**
   * @param node {osparc.data.model.Node} Node owning the widget
   */
  construct: function(node) {
    this.base(arguments);

    this.set({
      width: this.self().NODE_WIDTH,
      maxWidth: this.self().NODE_WIDTH,
      minWidth: this.self().NODE_WIDTH
    });

    this.setNode(node);

    this._createWindowLayout();
  },

  properties: {
    node: {
      check: "osparc.data.model.Node",
      nullable: false
    },

    thumbnail: {
      check: "String",
      nullable: true,
      apply: "_applyThumbnail"
    }
  },

  statics: {
    NODE_WIDTH: 200,
    NODE_HEIGHT: 80,
    CIRCLED_RADIUS: 16
  },

  members: {
    __progressBar: null,
    __thumbnail: null,

    getNodeType: function() {
      return "service";
    },

    getNodeId: function() {
      return this.getNode().getNodeId();
    },

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "chips": {
          control = new qx.ui.container.Composite(new qx.ui.layout.Flow(3, 3)).set({
            margin: [3, 4]
          });
          let nodeType = this.getNode().getMetaData().type;
          if (this.getNode().isContainer()) {
            nodeType = "container";
          }
          if (this.getNode().isIterator()) {
            nodeType = "iterator";
          }
          const type = osparc.utils.Services.getType(nodeType);
          if (type) {
            control.add(new osparc.ui.basic.Chip(type.label, type.icon + "12"));
          }
          this.add(control, {
            row: 1,
            column: 0
          });
          break;
        }
        case "progress":
          control = new qx.ui.indicator.ProgressBar().set({
            height: 10,
            margin: 4
          });
          this.add(control, {
            row: 2,
            column: 0
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    // overridden
    _createWindowLayout: function() {
      const node = this.getNode();
      if (node.getThumbnail()) {
        this.setThumbnail(node.getThumbnail());
      }
      this._inputOutputLayout = this.getChildControl("input-output");
      const chipContainer = this.getChildControl("chips");

      if (node.isComputational() || node.isFilePicker()) {
        this.__progressBar = this.getChildControl("progress");
      }

      const nodeStatus = new osparc.ui.basic.NodeStatusUI(node);
      chipContainer.add(nodeStatus);
    },

    populateNodeLayout: function() {
      const node = this.getNode();
      node.bind("label", this, "caption");
      if (node.isContainer()) {
        this.setIcon("@FontAwesome5Solid/folder-open/14");
      }
      const metaData = node.getMetaData();
      if ((metaData && metaData.inputs && Object.keys(metaData.inputs).length) || this.getNode().isContainer()) {
        this._createUIPorts(true);
      }
      if ((metaData && metaData.outputs && Object.keys(metaData.outputs).length) || this.getNode().isContainer()) {
        this._createUIPorts(false);
      }
      if (node.isComputational() || node.isFilePicker()) {
        node.getStatus().bind("progress", this.__progressBar, "value");
      }
      /*
      node.getStatus().bind("running", this, "decorator", {
        // Paint borders
        converter: state => osparc.utils.StatusUI.getBorderDecorator(state)
      });
      */
    },

    __hideExtraElements: function() {
      const chipContainer = this.getChildControl("chips");
      chipContainer.exclude();

      if (this.__progressBar) {
        this.__progressBar.exclude();
      }

      if (this._inputLayout && "ui" in this._inputLayout) {
        this._inputLayout.ui.exclude();
      }
    },

    turnIntoFileUI: function() {
      const outputs = this.getNode().getOutputs();
      if ([null, ""].includes(osparc.file.FilePicker.getOutput(outputs))) {
        // no output selected
        return;
      }

      const width = 120;
      this._turnIntoCircledUI(width, this.self().CIRCLED_RADIUS);
      this.__hideExtraElements();

      // two lines
      this.getChildControl("title").set({
        rich: true,
        wrap: true,
        maxHeight: 28,
        minWidth: width-16,
        maxWidth: width-16
      });

      let imageSrc = null;
      if (osparc.file.FilePicker.isOutputFromStore(outputs)) {
        imageSrc = "@FontAwesome5Solid/file-alt/34";
      } else if (osparc.file.FilePicker.isOutputDownloadLink(outputs)) {
        imageSrc = "@FontAwesome5Solid/link/34";
      }
      if (imageSrc) {
        const fileImage = new osparc.ui.basic.Thumbnail(imageSrc).set({
          padding: 12
        });
        this._inputOutputLayout.addAt(fileImage, 1, {
          flex: 1
        });
      }
      this.fireEvent("nodeMoving");
    },

    turnIntoParameterUI: function() {
      const width = 90;
      const radius = 32;
      this._turnIntoCircledUI(width, radius);
      this.__hideExtraElements();

      const label = new qx.ui.basic.Label().set({
        font: "text-22",
        allowGrowX: true,
        textAlign: "center",
        padding: 6
      });
      this._inputOutputLayout.addAt(label, 1, {
        flex: 1
      });

      const firstOutput = this.getNode().getFirstOutput();
      if (firstOutput && "value" in firstOutput) {
        const value = firstOutput["value"];
        label.setValue(String(value));
      }
      this.getNode().addListener("changeOutputs", e => {
        const updatedOutputs = e.getData();
        const newVal = updatedOutputs["out_1"];
        label.setValue(String(newVal["value"]));
      });
    },

    turnIntoIteratorPrimary: function(canvas) {
      const width = 150;
      this._turnIntoCircledUI(width, this.self().CIRCLED_RADIUS);

      const nShadows = 2;
      this.shadows = [];
      for (let i=0; i<nShadows; i++) {
        const nodeUIShadow = canvas.drawNodeUI(width, 62, this.self().CIRCLED_RADIUS);
        this.shadows.push(nodeUIShadow);
      }
    },

    turnIntoIteratorSnaphot: function() {
      const width = 120;
      this._turnIntoCircledUI(width, this.self().CIRCLED_RADIUS);
      this.__hideExtraElements();

      const firstOutput = this.getNode().getFirstOutput();
      if (firstOutput && "value" in firstOutput) {
        const value = firstOutput["value"];

        const label = new qx.ui.basic.Label(String(value)).set({
          font: "text-22",
          allowGrowX: true,
          textAlign: "center",
          padding: 6
        });
        this._inputOutputLayout.addAt(label, 1, {
          flex: 1
        });
      }
    },

    // overridden
    _createUIPorts: function(isInput) {
      const portLabel = this._createUIPortLabel(isInput);
      const label = {
        isInput: isInput,
        ui: portLabel
      };
      if (isInput) {
        this.getNode().getStatus().bind("dependencies", portLabel, "textColor", {
          converter: dependencies => {
            if (dependencies !== null) {
              return osparc.utils.StatusUI.getColor(dependencies.length ? "modified" : "ready");
            }
            return osparc.utils.StatusUI.getColor();
          }
        });
      } else {
        this.getNode().getStatus().bind("output", portLabel, "textColor", {
          converter: output => {
            switch (output) {
              case "up-to-date":
                return osparc.utils.StatusUI.getColor("ready");
              case "out-of-date":
              case "busy":
                return osparc.utils.StatusUI.getColor("modified");
              case "not-available":
              default:
                return osparc.utils.StatusUI.getColor();
            }
          }
        });
      }
      label.ui.isInput = isInput;
      this._addDragDropMechanism(label.ui, isInput);
      if (isInput) {
        this._inputLayout = label;
        this._inputOutputLayout.addAt(label.ui, 0, {
          flex: 1
        });
      } else {
        this._outputLayout = label;
        const nElements = this._inputOutputLayout.getChildren().length;
        this._inputOutputLayout.addAt(label.ui, nElements, {
          flex: 1
        });
        label.ui.addListener("tap", e => {
          this.__openNodeDataManager();
          e.preventDefault();
        }, this);
      }
    },

    // overridden
    _createDragDropEventData: function(e, isInput) {
      return {
        event: e,
        nodeId: this.getNodeId(),
        isInput: isInput
      };
    },

    __openNodeDataManager: function() {
      const nodeDataManager = new osparc.component.widget.NodeDataManager(this.getNode());
      const win = osparc.ui.window.Window.popUpInWindow(nodeDataManager, this.getNode().getLabel(), 900, 600).set({
        appearance: "service-window"
      });
      const closeBtn = win.getChildControl("close-button");
      osparc.utils.Utils.setIdToWidget(closeBtn, "nodeDataManagerCloseBtn");
    },

    // override qx.ui.core.MMovable
    _onMovePointerMove: function(e) {
      // Only react when dragging is active
      if (!this.hasState("move")) {
        return;
      }

      const coords = this._setPositionFromEvent(e);
      this.getNode().setPosition(coords);

      this.base(arguments, e);
    },

    _applyThumbnail: function(thumbnail, oldThumbnail) {
      if (oldThumbnail !== null) {
        this.removeAt(0);
      }
      if (osparc.utils.Utils.isUrl(thumbnail)) {
        this.__thumbnail = new qx.ui.basic.Image(thumbnail).set({
          height: 100,
          allowShrinkX: true,
          scale: true
        });
      } else {
        this.__thumbnail = new qx.ui.embed.Html(thumbnail).set({
          height: 100
        });
      }
      this.addAt(this.__thumbnail, 0);
    },

    // implement osparc.component.filter.IFilterable
    _shouldApplyFilter: function(data) {
      if (data.text) {
        const label = this.getNode().getLabel()
          .trim()
          .toLowerCase();
        if (label.indexOf(data.text) === -1) {
          return true;
        }
      }
      if (data.tags && data.tags.length) {
        const category = this.getNode().getMetaData().category || "";
        const type = this.getNode().getMetaData().type || "";
        if (!data.tags.includes(osparc.utils.Utils.capitalize(category.trim())) && !data.tags.includes(osparc.utils.Utils.capitalize(type.trim()))) {
          return true;
        }
      }
      return false;
    }
  }
});
