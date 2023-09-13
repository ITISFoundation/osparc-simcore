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

/**
 * @asset(osaprc/s4l_tours.json)
 */

qx.Class.define("osparc.product.tours.s4l.Tours", {
  extend: qx.ui.core.Widget,
  type: "singleton",

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(20));

    this.set({
      zIndex: 100000
    });

    /*
    osparc.utils.Utils.fetchJSON("/resource/osparc/s4l_tours.json")
      .then(tours => {
        console.log("tours", tours);
        this.setTours(tours);
      });
    */
  },

  properties: {
    tours: {
      check: "Array",
      init: [],
      nullable: true
    }
  },

  statics: {
    getTours: function() {
      return [{
        "id": "dashboard",
        "name": "Dashboard",
        "description": "Introduction to Dashboard tabs",
        "steps": [{
          "anchorEl": "osparc-test-id=studiesTabBtn",
          "beforeClick": {
            "selector": "osparc-test-id=studiesTabBtn"
          },
          "title": "Projects",
          "text": "Existing projects can be accessed and managed, and new projects can be created. Each project is represented by a card.",
          "placement": "bottom"
        }, {
          "anchorEl": "osparc-test-id=templatesTabBtn",
          "beforeClick": {
            "selector": "osparc-test-id=templatesTabBtn"
          },
          "title": "Tutorials",
          "text": "A set of pre-built tutorial projects with results is available to all users. When a tutorial is selected, a copy is automatically created and added to the user’s Projects tab. This new copy is editable.",
          "placement": "bottom"
        }]
      }];
    }
  }
});
