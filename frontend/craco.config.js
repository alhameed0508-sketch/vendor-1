// The dev proxy gzips text/event-stream and holds the first chunk back, so the live stream looks frozen.
module.exports = {
  devServer: { compress: false },
};
