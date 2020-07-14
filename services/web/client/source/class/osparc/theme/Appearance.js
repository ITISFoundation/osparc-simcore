/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Tobias Oetiker (oetiker)

************************************************************************ */

qx.Theme.define("osparc.theme.Appearance", {
  extend: osparc.theme.osparc.Appearance,

  appearances: {
    /*
    ---------------------------------------------------------------------------
      jsonforms
    ---------------------------------------------------------------------------
    */
    "form-array-container": {
      style: () => ({
        padding: 10,
        decorator: "border-editable"
      })
    },

    /*
    ---------------------------------------------------------------------------
      buttons
    ---------------------------------------------------------------------------
    */
    "toolbar-xl-button": {
      include: "toolbar-button",
      alias: "toolbar-button",
      style: state => ({
        allowStretchY: false,
        allowStretchX: false,
        minHeight: 50,
        center: true
      })
    },

    "toolbar-xl-button/label": {
      include: "toolbar-button/label",
      style: state => ({
        font: "title-16"
      })
    },

    "toolbar-lg-button": {
      include: "toolbar-button",
      alias: "toolbar-button",
      style: state => ({
        allowStretchY: false,
        allowStretchX: false,
        minHeight: 35,
        center: true
      })
    },

    "toolbar-lg-button/label": {
      include: "toolbar-button/label",
      style: state => ({
        font: "text-16"
      })
    },

    "toolbar-md-button": {
      include: "toolbar-button",
      alias: "toolbar-button",
      style: state => ({
        allowStretchY: false,
        allowStretchX: false,
        minHeight: 25,
        center: true
      })
    },

    "toolbar-md-button/label": {
      include: "toolbar-button/label",
      style: state => ({
        font: "text-14"
      })
    }
  }
});
