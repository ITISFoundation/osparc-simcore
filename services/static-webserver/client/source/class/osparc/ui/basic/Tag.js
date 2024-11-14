/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * GitHub-like tag.
 * It has a message and a background color.
 */
qx.Class.define("osparc.ui.basic.Tag", {
  extend: qx.ui.basic.Label,
  /**
   * Constructor for the Tag element.
   * @param {osparc.data.model.Tag} tag Short text to be shown on the tag
   * @param {String} [filterGroupId] If present, clicking on the tab will dispatch a bus message with the
   *    id ``GroupIdTagsTrigger`` to be subscribed by a filter.
   */
  construct: function(tag, filterGroupId) {
    this.base(arguments);

    if (tag) {
      tag.bind("name", this, "value");
      tag.bind("color", this, "color");
    }
    this.setFont("text-11");

    if (filterGroupId) {
      this.setCursor("pointer");
      this.addListener("tap", e => {
        e.stopPropagation();
        qx.event.message.Bus.dispatchByName(osparc.utils.Utils.capitalize(filterGroupId, "tags", "trigger"), this.getValue());
      }, this);
      // Stop propagation of the pointer event in case the tag is inside a button that we don't want to trigger
      this.addListener("pointerdown", e => e.stopPropagation());
    }
  },
  properties: {
    color: {
      check: "Color",
      apply: "_applyColor"
    },
    appearance: {
      init: "tag",
      refine: true
    }
  },
  members: {
    _applyColor: function(color) {
      this.setBackgroundColor(color);
      // Set the right color for the font
      const textColor = osparc.utils.Utils.getContrastedBinaryColor(color);
      this.setTextColor(textColor);
    }
  }
});
