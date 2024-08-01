import numpy as np
import matplotlib.pyplot as plt
from scipy import spatial
from scipy.interpolate import  splev, splprep
from pytransform3d.rotations import matrix_from_axis_angle
from scipy.spatial.transform import Rotation as Rot
import math
import vg
import operator
import statistics as stat


class tube_structure_analysis():
    """Class used to analyse tube-structures in terms of, spline_length, cranial caudal extension, width and width in z-plane"""
    def __init__(self, skagen_name, treatment):
        self.skagen_name = skagen_name
        self.treatment = treatment

        self.width_list = list()
        self.horizontal_width_list = list()

        self.structure_length = None
        self.cranial_caudal_extension = None

    
    def plot_planes(self, centroid_value_x, centroid_value_y, z_coordinate):
        """ Function that gives us the plane and spline-length (so cummulative length of the structure)"""
        tck, u = splprep([centroid_value_x, centroid_value_y, z_coordinate], s = 0, k = 2)

        evalpts = np.linspace(0, 1, len(centroid_value_x))

        pts = splev(evalpts, tck)

        structure_length = self.length_of_spline(pts[0], pts[1], pts[2])


        scale = self.SplineTube(centroid_value_x, centroid_value_y, z_coordinate, n = len(centroid_value_x)+50)

        return (scale, structure_length)

    def SplineTube(self, centroid_value_x, centroid_value_y, z_coordinate, n, degree = 2, **kwargs):
        """This function returns the scaling needed to get the 'true' width of the structure"""
        assert n >= 3
        scale_list = list()
        (tck, u), fp, ier, msg = splprep([centroid_value_x, centroid_value_y, z_coordinate], s=0, k=2, full_output=True)

        evalpts = np.linspace(0,1,n)

        pts = np.array(splev(evalpts, tck))
        der = np.array(splev(evalpts, tck, der=1))

        _points = np.array(
            [[0, 0, 0],
        [0, 1, 0],
        [1, 1, 0],
        [1, 0, 0]],
    ) - np.array([0.5, 0.5, 0])
        _normal = np.array([0, 0, 1])   

        points = []
        for i in range(n):
            points_slice, scale, angle = self._rotmat(der[:,i], _points)
            #angle_deg = math.degrees(angle)
            scale_list.append(scale)
            points_slice = points_slice + pts[:,i]
            points.append(points_slice)
        
        points = np.stack(points)

        return (scale_list)
    
    def _rotmat(self, vector, points):
        """This function gives the roation matrix for the rotation of the plane"""
        #This function delivers the rotation matrix
        #Input:The vector we want to rotate around and the points
        #     (assuming our planes in the beginning are horizontal with x and y axis)
        #Output: The rotation matrix, and the scaling factor we want to add to the existing a length,
        #       to get the correct length

        vector = vg.normalize(vector)
        axis = vg.perpendicular(vg.basis.z, vector)
        angle = vg.angle(vg.basis.z, vector, units='rad')
        scale = math.cos(angle)

        a = np.hstack((axis, (angle)))
        R = matrix_from_axis_angle(a)

        r = Rot.from_matrix(R)
        rotmat = r.apply(points)

        return rotmat, scale, angle

    def length_of_spline(self,x, y, z):
        """This function returns the cummulative length of the spline"""
        distance = 0
        for i in range(len(x)):
            if i == 0:
                continue
            else:
                dist = math.sqrt((x[i]-x[i-1])**2 + (y[i]-y[i-1])**2 + (z[i]-z[i-1])**2)
                distance = distance + dist
        return (distance)
    
    def longest_distance(self, x, y):
        """This function return the longest distance between coordinates in a plane"""
        matrix = np.column_stack((x,y))
        candidates = matrix[spatial.ConvexHull(matrix).vertices]
        dist_mat = spatial.distance_matrix(candidates, candidates)
        i, j = np.unravel_index(dist_mat.argmax(), dist_mat.shape)
        coord = [candidates[i], candidates[j]]
        x_cands = list()
        y_cands = list()
        for n in coord:
            x_cand = n[0]
            y_cand = n[1]
            x_cands.append(x_cand)
            y_cands.append(y_cand)
        dist = math.sqrt((x_cands[1]-x_cands[0])**2 + (y_cands[1]-y_cands[0])**2)

        return (dist)

    def get_width(self, plot_structure = None):
        """Gives the 'real' width of a tube-like structure, by rotation each horizontal slide to be perpendicular with the direction of the spline"""
        #This function calculates the centroid value in every CT-slice. 
        #It then fits a spline to the centroid values from every slice (currently with the smoothness parameter = 0)
        #It calculates the direction vector for every point in the spline. The horizontal(z) coordinate-plane is 
        #angled to be perpendicular with the direction vector. The angle between the horizontal(z) coordinate-plane
        #and the plane perpendicular to the direction vector is used to scale the horizontal width, to give a
        #'true' value
        #       Input:      Coordinate set of the structure of interest in the following format: [[[x,y,z],...,[xn,yn,z]],...[[x,y,zn],...,[xn,yn,zn]]
        #                   True/False if you want to plot/not plot the structure spline 
        #       Output:     The width
        #counter = 0
        centroid_value_x = list()
        centroid_value_y = list()
        z_coordinate = list()
        
        coordinate_list = self.treatment.coordinate_list
        #coordinate_list = rtclass.self.treatment.get_coordinates(self.skagen_name)

        for plane in coordinate_list:
            #counter = counter + 1
            all_points_list = list()
            count = 0
            for i in plane:
                all_points = [i[0],i[1]]
                all_points_list.append(all_points)
                count = count + 1
            
            all_points_arr = np.array(all_points_list)

            x_coordinate = all_points_arr[:,0]
            y_coordinate = all_points_arr[:,1]
            z_coordinate.append(plane[0][2])

            dist = self.longest_distance(x_coordinate, y_coordinate)
            self.horizontal_width_list.append(dist)

            centroid_value_x.append(stat.mean(x_coordinate))
            centroid_value_y.append(stat.mean(y_coordinate))


        #Sorting the values by z, to ensure correct order in the spline
        Matrix = sorted(zip(centroid_value_x, centroid_value_y, z_coordinate), key=operator.itemgetter(2))
        centroid_value_x, centroid_value_y, z_coordinate = zip(*Matrix)

        #Calculating the distance between the points, to discard outliers
        outlier_list = list()
        centroid_value_x_without_outliers = list()
        centroid_value_y_without_outliers = list()
        z_coordinate_without_outliers = list()
        for i in range(len(z_coordinate)-1):
            distance_outlier_test = math.sqrt((centroid_value_x[i+1]-centroid_value_x[i])**2 + (centroid_value_y[i+1]-centroid_value_y[i])**2 + (z_coordinate[i+1]-z_coordinate[i])**2)
            if distance_outlier_test <= 80:
                centroid_value_x_without_outliers.append(centroid_value_x[i])
                centroid_value_y_without_outliers.append(centroid_value_y[i])
                z_coordinate_without_outliers.append(z_coordinate[i])
                outlier_list.append('No')
            elif distance_outlier_test > 80 and i == 0:
                outlier_list.append('Outlier')
            elif distance_outlier_test > 80 and i !=0:
                outlier_list.append('Outlier')
                print('outlier detected, removed from further calculations')
                break
        
        #Sorting again to make sure, that we have the correct order

        Matrix_2 = sorted(zip(centroid_value_x_without_outliers, centroid_value_y_without_outliers, z_coordinate_without_outliers), key=operator.itemgetter(2))
        centroid_value_x, centroid_value_y, z_coordinate = zip(*Matrix_2)

    
        #Removing/stopping the calculations, if there is only 3 planes pressent in the structure

        if len(centroid_value_x) <= 3:
            print('Not enough datapoints, only', len(centroid_value_x), 'planes drawn')
            self.width_list = 0
            self.structure_length = 0
            centroid_matrix = 0
        else:

            centroid_matrix = [centroid_value_x,centroid_value_y,z_coordinate]

            if plot_structure is True:
                fig = plt.figure(figsize=(12,10))
                ax = plt.axes(projection='3d')
                ax.plot(centroid_matrix[0], centroid_matrix[1], centroid_matrix[2], lw = 2, c= 'coral')
                ax.plot(centroid_value_x, centroid_value_y, z_coordinate,'.')
                ax.view_init(0,0)
                plt.show()
        
            scale, self.structure_length = self.plot_planes(centroid_value_x, centroid_value_y,z_coordinate)
            for l, k in zip(self.horizontal_width_list, scale):
                width = abs(l*k)
                self.width_list.append(width)


        return (self.width_list, self.structure_length, self.horizontal_width_list)

    def get_cranial_caudal_extension(self):
        """ This function returns the cranial caudal extension of a given structure (In other words: the extension of the structure in the z-direction"""
        if len(self.treatment.plane_list) <= 3:
            print('To few planes')
        else:
            self.cranial_caudal_extension = (len(self.treatment.plane_list)-1)*self.treatment.slice_thickness ## mm
        return (self.cranial_caudal_extension)
    

    
    

        


