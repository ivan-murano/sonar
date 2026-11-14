# Copia di src/prediction_features.py del modello (14/11/2026), usata solo come riferimento nei test.
"""Feature geometriche equivalenti al benchmark con indici riutilizzati."""
import numpy as np
import pandas as pd
import shapely

class SpatialFeatureContext:
    def __init__(self,roads,buildings,osm,places):
        self.roads=roads.geometry.to_numpy();self.roadtree=shapely.STRtree(self.roads);self.lengths=shapely.length(self.roads)
        self.buildings=buildings.geometry.to_numpy();self.buildtree=shapely.STRtree(self.buildings);self.areas=shapely.area(self.buildings)
        motor=['motorway','trunk','primary','secondary','tertiary','residential','unclassified','living_street','service']
        roadkind=roads.highway.str.replace('_link','',regex=False)
        self.major=roadkind.isin(motor[:5]).to_numpy();self.motor=roadkind.isin(motor).to_numpy()
        self.pois={name:(frame,shapely.STRtree(frame.geometry.to_numpy())) for name,frame in [('osm',osm),('ovt',places)]}

    def compute(self,points,radii=(100,250,500)):
        x=pd.DataFrame(index=range(len(points)))
        for radius in radii:
            buffers=points.buffer(radius).to_numpy()
            candidates=self.roadtree.query(buffers,predicate='intersects')
            idx=candidates[1];covered=shapely.covered_by(self.roads[idx],buffers[candidates[0]])
            lengths=self.lengths[idx].copy();partial=~covered
            lengths[partial]=shapely.length(shapely.intersection(self.roads[idx[partial]],buffers[candidates[0,partial]]))
            x[f'road_all_m_{radius}']=np.bincount(candidates[0],weights=lengths,minlength=len(points))
            for name,mask in [('major',self.major),('motor',self.motor)]:
                selected=mask[idx];x[f'road_{name}_m_{radius}']=np.bincount(candidates[0,selected],weights=lengths[selected],minlength=len(points))
            candidates=self.buildtree.query(buffers,predicate='intersects');idx=candidates[1]
            covered=shapely.covered_by(self.buildings[idx],buffers[candidates[0]])
            areas=self.areas[idx].copy();partial=~covered
            areas[partial]=shapely.area(shapely.intersection(self.buildings[idx[partial]],buffers[candidates[0,partial]]))
            x[f'building_cover_{radius}']=np.bincount(candidates[0],weights=areas,minlength=len(points))/(np.pi*radius**2)
            for source,(pois,tree) in self.pois.items():
                candidates=tree.query(points.to_numpy(),predicate='dwithin',distance=radius)
                x[f'{source}_poi_all_{radius}']=np.bincount(candidates[0],minlength=len(points))
                for group in ['nightlife','food','education','retail','health','leisure','transport','business','other']:
                    selected=pois.group.to_numpy()[candidates[1]]==group
                    x[f'{source}_{group}_{radius}']=np.bincount(candidates[0,selected],minlength=len(points))
                if source=='osm':
                    selected=pois.opening_hours.notna().to_numpy()[candidates[1]]
                    x[f'osm_hours_known_{radius}']=np.bincount(candidates[0,selected],minlength=len(points))
        return x
