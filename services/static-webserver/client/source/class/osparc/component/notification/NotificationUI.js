/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.component.notification.NotificationUI", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this.set({
      maxWidth: this.self().MAX_WIDTH,
      padding: this.self().PADDING
    });

    const layout = new qx.ui.layout.VBox(2).set({
      alignY: "middle"
    });
    this._setLayout(layout);

    this.getChildControl("title");
    this.getChildControl("text");
    this.getChildControl("date");

    this.bind("read", this, "backgroundColor", {
      converter: read => read ? "background-main-3" : "background-main-4"
    });
  },

  properties: {
    id: {
      check: "String",
      init: null,
      nullable: false,
      event: "changeId"
    },

    category: {
      check: ["new_organization", "study_shared", "template_shared"],
      init: null,
      nullable: false,
      event: "changeCategory"
    },

    actionablePath: {
      check: "String",
      init: null,
      nullable: false,
      event: "changeActionablePath",
      apply: "__applyActionablePath"
    },

    title: {
      check: "String",
      init: null,
      nullable: false,
      event: "changeTitle"
    },

    text: {
      check: "String",
      init: null,
      nullable: false,
      event: "changeText"
    },

    date: {
      check: "Date",
      init: null,
      nullable: false,
      event: "changeDate"
    },

    read: {
      check: "Boolean",
      init: false,
      nullable: false,
      event: "changeRead"
    }
  },

  statics: {
    MAX_WIDTH: 300,
    PADDING: 10
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "title":
          control = new qx.ui.basic.Label().set({
            font: "text-14",
            rich: true,
            wrap: true
          });
          this.bind("title", control, "value");
          this._add(control, {
            flex: 1
          });
          break;
        case "text":
          control = new qx.ui.basic.Label().set({
            font: "text-13",
            rich: true,
            wrap: true
          });
          this.bind("text", control, "value");
          this._add(control, {
            flex: 1
          });
          break;
        case "date":
          control = new qx.ui.basic.Label().set({
            font: "text-12",
            rich: true,
            wrap: true
          });
          this.bind("date", control, "value", {
            converter: value => {
              if (value) {
                return osparc.utils.Utils.formatDateAndTime(new Date(value));
              }
              return "";
            }
          });
          this._add(control, {
            flex: 1
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __applyActionablePath: function(value) {
      console.log("actionablePath", value);
    }
  }
});
