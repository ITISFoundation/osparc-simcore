qx.Class.define("qxapp.components.widgets.CollapsableVBox", {
  extend: qx.ui.core.Widget,

  construct: function(headerText = "Header", contentWidgets = []) {
    this.base(arguments);

    let widgetLayout = new qx.ui.layout.VBox(5);
    this._setLayout(widgetLayout);

    // header
    {
      let header = this.__headerBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
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
      expandBtn.addListener("execute", function(e) {
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
    this.setCollapsed(true);
  },

  properties: {
    collapsed: {
      nullable: false,
      check: "Boolean",
      init: true,
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
    __headerLabelExpanded: null,
    __headerLabelCollapsed: null,
    __contentWidgets: null,

    __buildLayout: function(collapse) {
      this.__headerBox.removeAll();
      this.__contentBox.removeAll();

      this.__headerBox.add(this.__expandBtn);
      if (collapse) {
        // content
        for (let i = 0; i < this.__headerLabelCollapsed.length; i++) {
          let charLabel = this.__headerLabelCollapsed[i];
          this.__contentBox.add(charLabel);
        }
        this.setWidth(24);
      } else {
        // header
        this.__headerBox.add(this.__headerLabelExpanded, {
          flex: 1
        });
        // content
        this.__contentBox.removeAll();
        for (let i = 0; i < this.__contentWidgets.length; i++) {
          let widget = this.__contentWidgets[i].widget;
          let map = this.__contentWidgets[i].map;
          this.__contentBox.add(widget, map);
        }
        this.setWidth(this.getMaxWidth());
      }
    },

    rebuildLayout: function() {
      this.__buildLayout(this.getCollapsed());
    },

    __applyHeaderText: function(newHeader) {
      if (this.__headerLabelExpanded === null) {
        this.__headerLabelExpanded = new qx.ui.basic.Label(newHeader).set({
          textAlign: "center"
        });
      }
      this.__headerLabelExpanded.setValue(newHeader);

      this.__headerLabelCollapsed = [];
      for (let i = 0; i < newHeader.length; i++) {
        let charLabel = new qx.ui.basic.Label(newHeader.charAt(i)).set({
          textAlign: "center"
        });
        this.__headerLabelCollapsed.push(charLabel);
      }

      this.rebuildLayout();
    },

    getContentWidgets: function() {
      return this.__contentWidgets;
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
    }
  }
});
