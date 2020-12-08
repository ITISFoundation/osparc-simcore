/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget that displays a score in form of stars.
 * It can also show the score with the max score next to it "87/100"
 */
qx.Class.define("osparc.ui.basic.StarsRating", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox(5).set({
      alignY: "middle"
    }));
  },

  properties: {
    score: {
      check: "Number",
      init: 1,
      nullable: false,
      apply: "__render"
    },

    maxScore: {
      check: "Number",
      init: 5,
      nullable: false,
      apply: "__render"
    },

    nStars: {
      check: "Number",
      init: 5,
      nullable: false,
      apply: "__render"
    },

    showEmptyStars: {
      check: "Boolean",
      init: false,
      nullable: false,
      apply: "__render"
    },

    showScore: {
      check: "Boolean",
      init: false,
      nullable: false,
      apply: "__render"
    }
  },

  statics: {
    StarFull: "@FontAwesome5Solid/star/12",
    StarHalf: "@FontAwesome5Solid/star-half/12", // Todo: upgrade FontAwesome for star-half-alt
    StarEmpty: "@FontAwesome5Regular/star/12"
  },

  members: {
    // overridden
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "stars-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(0));
          this._add(control);
          break;
        case "score-text": {
          control = new qx.ui.basic.Label().set({
            font: "text-12"
          });
          this._add(control);
          break;
        }
      }

      return control || this.base(arguments, id);
    },

    __checkValues: function() {
      const score = this.getScore();
      const maxScore = this.getMaxScore();
      if (score && maxScore && score >= 0 && score <= maxScore) {
        return true;
      }
      return false;
    },

    __render: function() {
      if (this.__checkValues()) {
        this.__renderStars();
        this.__renderScore();
      }
    },

    __renderStars: function() {
      const starsLayout = this.getChildControl("stars-layout");
      starsLayout.removeAll();

      const score = this.getScore();
      const maxScore = this.getMaxScore();
      const maxStars = this.getNStars();
      const normScore = score/maxScore;

      const fullStars = Math.floor(normScore/(1.0/maxStars));
      for (let i=0; i<fullStars; i++) {
        const star = new qx.ui.basic.Image(this.self().StarFull);
        starsLayout.add(star);
      }

      const halfStar = Math.round((normScore%(1.0/maxStars))*maxStars);
      for (let i=0; i<halfStar; i++) {
        const star = new qx.ui.basic.Image(this.self().StarHalf);
        starsLayout.add(star);
      }

      const emptyStars = maxStars - fullStars - halfStar;
      if (this.getShowEmptyStars()) {
        for (let i=0; i<emptyStars; i++) {
          const star = new qx.ui.basic.Image(this.self().StarEmpty);
          starsLayout.add(star);
        }
      } else if (fullStars === 0 && halfStar === 0) {
        const star = new qx.ui.basic.Image(this.self().StarEmpty);
        starsLayout.add(star);
      }
    },

    __renderScore: function() {
      const scoreText = this.getChildControl("score-text");
      if (this.getShowScore()) {
        const score = this.getScore().toString();
        const maxScore = this.getMaxScore().toString();
        scoreText.setValue(`${score}/${maxScore}`);
        scoreText.show();
      } else {
        scoreText.exclude();
      }
    }
  }
});
