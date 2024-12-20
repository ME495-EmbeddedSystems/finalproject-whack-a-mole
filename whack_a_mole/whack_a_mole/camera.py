import cv2
from cv_bridge import CvBridge
from geometry_msgs.msg import TransformStamped
import numpy as np

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile
from sensor_msgs.msg import CameraInfo, Image
from std_srvs.srv import Empty
from tf2_ros import TransformBroadcaster

from whack_a_mole.constants import COLORS, COLORS_HSV
from whack_a_mole.mole_detection import OpenCVClient


class Camera(Node):
    """
    Camera node that detects the color of the object and broadcasts the frame.

    **Parameters**:
        clipping_distance (int): The clipping distance for the depth image
        box_start_x (int): The starting x coordinate for the bounding box
        box_end_x (int): The ending x coordinate for the bounding box
        box_start_y (int): The starting y coordinate for the bounding box
        box_end_y (int): The ending y coordinate for the bounding box

    **Publisher**:
        filtered_image (Image): The filtered image

    **Subscriber**:
        /camera/camera/aligned_depth_to_color/image_raw (Image): The depth image
        /camera/camera/color/image_raw (Image): The color image
        /camera/camera/color/camera_info (CameraInfo): The camera info

    **Service**:
        toggle_tf_publish (Empty): Toggles the update_colors variable
    """

    def __init__(self):
        """Initialize the Camera node."""
        super().__init__('color_camera')

        self.declare_parameter('clipping_distance', 1400)
        self.declare_parameter('box_start_x', 1)
        self.declare_parameter('box_end_x', 1)
        self.declare_parameter('box_start_y', 1)
        self.declare_parameter('box_end_y', 1)

        self.crop = [
            [
                self.get_parameter('box_start_x').value,
                self.get_parameter('box_start_y').value
            ],
            [
                self.get_parameter('box_end_x').value,
                self.get_parameter('box_end_y').value
            ]
        ]

        self.create_subscription(
            Image,
            '/camera/camera/aligned_depth_to_color/image_raw',
            self.get_depth_info,
            qos_profile=QoSProfile(depth=10),
        )

        self.create_subscription(
            Image,
            '/camera/camera/color/image_raw',
            self.get_color_info,
            qos_profile=QoSProfile(depth=10),
        )

        self.image_pub = self.create_publisher(
            Image, 'filtered_image', qos_profile=QoSProfile(depth=10)
        )

        self.camera_info_subscription = self.create_subscription(
            CameraInfo,
            '/camera/camera/color/camera_info',
            self.camera_info_callback,
            10,
        )

        self.create_service(Empty, 'toggle_tf_publish', self.toggle_tf_publish)

        self.clipping_distance = self.get_parameter('clipping_distance').value

        self.tf_broadcaster = TransformBroadcaster(self, qos=QoSProfile(depth=10))

        self.prev_xyz = np.array([0, 0, 0], dtype=float)

        self.freq = 30.0  # Hz

        self.create_timer(1 / self.freq, self.timer_callback)

        self.cv2_client = OpenCVClient(
            freq=self.freq,
            clipping_distance=self.clipping_distance,
            crop=self.crop
        )

        # If set to true update color tf frames
        self.update_colors = True

    def timer_callback(self):
        """
        Timer callback that detects the color of the object and broadcasts the frame.

        :arg None: No arguments required for this function.
        :type None: NoneType
        """
        if self.cv2_client.color_image.shape[0] == 0 or self.cv2_client.depth_image.shape[0] == 0:
            return

        for color in COLORS_HSV.keys():

            self.broadcast_color(
                lower_HSV=COLORS_HSV[color][0],
                higher_HSV=COLORS_HSV[color][1],
                color=color,
            )

            self.cv2_client.detect_illumination(color)

    def toggle_tf_publish(self, request, response):
        """
        Toggles the `update_colors` variable to start/stop publishing the color frames.

        :arg request: Empty request.
        :type request: `Empty.Request`
        :arg response: Empty response.
        :type response: `Empty.Response`

        :return: Returns the response.
        :rtype: `Empty.Response`
        """
        self.update_colors = not self.update_colors
        return response

    def broadcast_color(self, lower_HSV, higher_HSV, color: str):
        """
        Broadcasts the color frame based on HSV range.

        :arg lower_HSV: The lower HSV range.
        :type lower_HSV: numpy.array
        :arg higher_HSV: The higher HSV range.
        :type higher_HSV: numpy.array
        :arg color: The name of the color of the object.
        :type color: str
        """
        color_index = COLORS[color]

        x_c, y_c = self.find_color_centroid(lower_HSV, higher_HSV)

        if x_c != 0 and y_c != 0 and self.update_colors:

            self.cv2_client.running_avg[color_index, :-1] = self.cv2_client.running_avg[
                color_index, 1:
            ]  # Shift all elements down by 1
            self.cv2_client.running_avg[color_index, -1] = np.array([x_c, y_c])

        median_centroid = np.median(self.cv2_client.running_avg[color_index], axis=0)
        median_centroid = np.array(median_centroid, dtype=int)

        self.broadcast_color_frame(
            'camera_depth_frame', color + '_frame', median_centroid[0], median_centroid[1]
        )

    def find_color_centroid(self, lower_HSV: np.array, higher_HSV: np.array):
        """
        Find the pixel indices of the centroid of a color defined in the given HSV range.

        :arg lower_HSV: The lower HSV range for the color.
        :type lower_HSV: numpy.array
        :arg higher_HSV: The higher HSV range for the color.
        :type higher_HSV: numpy.array

        :return: The (x, y) centroid of the color.
        :rtype: tuple(int, int)
        """
        depth_image_3d = np.dstack(
            (self.cv2_client.depth_image, self.cv2_client.depth_image, self.cv2_client.depth_image)
        )  # depth image is 1 channel, color is 3 channels
        bg_removed = np.where(
            (depth_image_3d > self.clipping_distance) | (depth_image_3d <= 0),
            0,
            self.cv2_client.color_image,
        )
        if lower_HSV.shape[0] == 2:
            mask1 = cv2.inRange(
                cv2.cvtColor(bg_removed, cv2.COLOR_BGR2HSV), lower_HSV[0], higher_HSV[0]
            )
            mask2 = cv2.inRange(
                cv2.cvtColor(bg_removed, cv2.COLOR_BGR2HSV), lower_HSV[1], higher_HSV[1]
            )
            mask = mask1 + mask2
        else:
            mask = cv2.inRange(
                cv2.cvtColor(bg_removed, cv2.COLOR_BGR2HSV), lower_HSV, higher_HSV
            )
        if not np.any(mask):
            return np.array([-1, -1])

        # Find Centroid
        x_c, y_c = self.cv2_client.find_centroid_cropped(mask, (*self.crop[0], *self.crop[1]))
        x_c = int(x_c)
        y_c = int(y_c)
        for color in COLORS:
            color_index = COLORS[color]
            avg_centroid = np.median(self.cv2_client.running_avg[color_index], axis=0)
            avg_centroid = np.array(avg_centroid, dtype=int)
            cv2.circle(
                bg_removed,
                (avg_centroid[0], avg_centroid[1]),
                5,
                (0, 0, 255),
                thickness=10,
            )
            cv2.putText(
                bg_removed,
                f'{color}',
                (avg_centroid[0], avg_centroid[1]),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (255, 255, 255),
                2,
            )
        cv2.rectangle(bg_removed, self.crop[0], self.crop[1], (0, 0, 255), thickness=5)
        msg = CvBridge().cv2_to_imgmsg(bg_removed, encoding='bgr8')
        self.image_pub.publish(msg)
        return x_c, y_c

    def log(self, *message):
        """
        Log custom messages.

        :arg message: The message(s) to log.
        :type message: str
        """
        self.get_logger().info(f'[CAMERA NODE]: {", ".join(str(i) for i in message)}')

    def camera_info_callback(self, msg):
        """
        Publish new camera hardware info.

        :arg msg: The `CameraInfo` message containing intrinsic parameters.
        :type msg: `CameraInfo`
        """
        self.cv2_client.camera_intrinsics = msg.k

    def get_depth_info(self, msg: Image):
        """
        Publish new camera depth info.

        :arg msg: The depth image message.
        :type msg: `Image`
        """
        self.cv2_client.depth_image = CvBridge().imgmsg_to_cv2(msg)

    def get_color_info(self, msg: Image):
        """
        Publish new camera color info.

        :arg msg: The color image message.
        :type msg: `Image`
        """
        self.cv2_client.color_image = CvBridge().imgmsg_to_cv2(msg, desired_encoding='bgr8')

    def broadcast_color_frame(self, base_frame, child_frame, x_c, y_c):
        """
        Broadcasts the transform for a detected color frame.

        :arg base_frame: The base frame's name.
        :type base_frame: str
        :arg child_frame: The child frame's name.
        :type child_frame: str
        :arg x_c: The x-coordinate of the detected color's centroid in the image.
        :type x_c: int
        :arg y_c: The y-coordinate of the detected color's centroid in the image.
        :type y_c: int
        """
        x, y, z = self.cv2_client.get_3d_coordinates_at_pixel(x_c, y_c, frame_name=child_frame)
        if x == -1:
            x, y, z = self.prev_xyz[0], self.prev_xyz[1], self.prev_xyz[2]
        else:
            self.prev_xyz[0], self.prev_xyz[1], self.prev_xyz[2] = x, y, z

        transform = TransformStamped()

        transform.header.stamp = self.get_clock().now().to_msg()
        transform.header.frame_id = base_frame
        transform.child_frame_id = child_frame

        transform.transform.translation.x = z
        transform.transform.translation.y = -x
        transform.transform.translation.z = -y

        transform.transform.rotation.x = 0.0
        transform.transform.rotation.y = 0.0
        transform.transform.rotation.z = 0.0
        transform.transform.rotation.w = 1.0

        self.tf_broadcaster.sendTransform(transform)


def entry(args=None):
    """
    Entry point for starting the ROS2 Camera node.

    :arg args: The arguments passed for initialization.
    :type args: list or NoneType
    """
    rclpy.init(args=args)

    camera_node = Camera()

    rclpy.spin(camera_node)
