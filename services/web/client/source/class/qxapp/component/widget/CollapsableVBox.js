qx.Class.define("qxapp.component.widget.CollapsableVBox", {
  extend: qx.ui.core.Widget,

  construct: function(headerText = "Header", contentWidgets = []) {
    this.base(arguments);

    let widgetLayout = new qx.ui.layout.VBox(5);
    this._setLayout(widgetLayout);

    // header
    {
      let header = this.__headerBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
        alignY: "middle"
      }));
      this._add(header);

      const icon = "@FontAwesome5Solid/expand-arrows-alt/24";
      let expandBtn = this.__expandBtn = new qx.ui.form.Button().set({
        icon: icon,
        allowGrowX: false,
        allowGrowY: false,
        maxWidth: 24,
        maxHeight: 24,
        padding: 0
      });
      expandBtn.addListener("execute", e => {
        this.toggleCollapsed();
      }, this);
    }

    // content
    {
      let content = this.__contentBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
      this._add(content, {
        flex: 1
      });

      this.setContentWidgets(contentWidgets);
    }

    this.setHeaderText(headerText);
    this.setCollapsed(false);
  },

  properties: {
    collapsed: {
      nullable: false,
      check: "Boolean",
      init: false,
      apply: "__buildLayout"
    },
    headerText: {
      check: "String",
      init: "",
      apply: "__applyHeaderText"
    }
  },

  events: {},

  members: {
    __headerBox: null,
    __contentBox: null,
    __expandBtn: null,
    __headerLabel: null,
    __contentWidgets: null,

    __buildLayout: function(collapse) {
      // header
      this.__headerBox.removeAll();
      this.__headerBox.add(this.__expandBtn);
      this.__headerBox.add(new qx.ui.core.Spacer(), {
        flex: 1
      });
      this.__headerBox.add(this.__headerLabel);
      this.__headerBox.add(new qx.ui.core.Spacer(), {
        flex: 3
      });

      // content
      this.__contentBox.removeAll();
      if (collapse) {
        this.__contentBox.setVisibility("excluded");
      } else {
        this.__contentBox.setVisibility("visible");
        for (let i = 0; i < this.__contentWidgets.length; i++) {
          let widget = this.__contentWidgets[i].widget;
          let map = this.__contentWidgets[i].map;
          this.__contentBox.add(widget, map);
        }
        // this.setWidth(this.getMaxWidth());
      }
    },

    rebuildLayout: function() {
      this.__buildLayout(this.getCollapsed());
    },

    __applyHeaderText: function(newHeader) {
      if (this.__headerLabel === null) {
        this.__headerLabel = new qx.ui.basic.Label(newHeader).set({
          textAlign: "center"
        });
      }
      this.__headerLabel.setValue(newHeader);
      this.rebuildLayout();
    },

    setContentWidgets: function(widgets) {
      if (Array.isArray(widgets) != true) {
        // Type check: Make sure it is a valid array
        throw new Error("Invalid type: Need a valid array");
      }

      this.__contentWidgets = widgets;
    },

    addContentWidget: function(widget, map) {
      this.__contentWidgets.push({
        widget: widget,
        map: map
      });

      this.rebuildLayout();
    }
  }
});
