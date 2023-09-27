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

qx.Class.define("osparc.tours.List", {
  extend: qx.ui.core.Widget,

  construct: function(tours) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(8));

    this.getChildControl("tours-layout");

    if (tours) {
      this.setTours(tours);
    }
  },

  events: {
    "tourSelected": "qx.event.type.Data"
  },

  properties: {
    tours: {
      check: "Array",
      init: [],
      nullable: true,
      event: "changeTours",
      apply: "__applyTours"
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "tours-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __isSelectorVisible: function(doc, selector) {
      const domEl = doc.querySelector(`[${selector}]`);
      if (domEl) {
        const domWidget = qx.ui.core.Widget.getWidgetByElement(domEl);
        if (qx.ui.core.queue.Visibility.isVisible(domWidget)) {
          return true;
        }
      }
      return false;
    },

    __getTourButton: function(tour) {
      let label = tour.name;
      if (tour.description) {
        label += "<br>" + tour.description;
      }
      const seqButton = new qx.ui.form.Button().set({
        label,
        icon: "@FontAwesome5Solid/arrow-right/14",
        iconPosition: "right",
        textAlign: "left",
        rich: true,
        wrap: true
      });
      seqButton.addListener("execute", () => this.fireDataEvent("tourSelected", tour), this);
      return seqButton;
    },

    __applyTours: function(tours) {
      const toursLayout = this.getChildControl("tours-layout");
      tours.forEach(tour => toursLayout.add(this.__getTourButton(tour)));
    }
  }
});
