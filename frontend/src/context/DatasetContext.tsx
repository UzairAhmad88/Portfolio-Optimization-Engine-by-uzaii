import React, { createContext, useContext, useEffect, useState } from 'react';
import { apiClient } from '../api/client';
import type { AssetMetadata, DatasetMetadataResponse, HealthResponse } from '../types/api';

interface DatasetContextType {
  currentDataset: DatasetMetadataResponse | null;
  setCurrentDataset: (dataset: DatasetMetadataResponse | null) => void;
  savedDatasets: DatasetMetadataResponse[];
  refreshSavedDatasets: () => Promise<void>;
  isLoadingDatasets: boolean;
  availableAssets: AssetMetadata[];
  setAvailableAssets: (assets: AssetMetadata[]) => void;
  isLoadingAssets: boolean;
  refreshAssets: (datasetId: string) => Promise<void>;
  apiHealth: HealthResponse | null;
  checkHealth: () => Promise<void>;
}

const DatasetContext = createContext<DatasetContextType | undefined>(undefined);

export const DatasetProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [currentDataset, setCurrentDataset] = useState<DatasetMetadataResponse | null>(null);
  const [savedDatasets, setSavedDatasets] = useState<DatasetMetadataResponse[]>([]);
  const [isLoadingDatasets, setIsLoadingDatasets] = useState<boolean>(false);
  const [availableAssets, setAvailableAssets] = useState<AssetMetadata[]>([]);
  const [isLoadingAssets, setIsLoadingAssets] = useState<boolean>(false);
  const [apiHealth, setApiHealth] = useState<HealthResponse | null>(null);

  const checkHealth = async () => {
    try {
      const health = await apiClient.getHealth();
      setApiHealth(health);
    } catch {
      setApiHealth(null);
    }
  };

  const refreshSavedDatasets = async () => {
    setIsLoadingDatasets(true);
    try {
      const list = await apiClient.listDatasets();
      setSavedDatasets(list);
      // If no active dataset is currently selected but persistent datasets exist, select the most recent
      setCurrentDataset((prev) => {
        if (prev) {
          const stillExists = list.find((d) => d.dataset_id === prev.dataset_id);
          return stillExists || (list.length > 0 ? list[0] : null);
        }
        return list.length > 0 ? list[0] : null;
      });
    } catch (err) {
      console.error('Failed to load saved datasets:', err);
    } finally {
      setIsLoadingDatasets(false);
    }
  };

  const refreshAssets = async (datasetId: string) => {
    if (!datasetId) return;
    setIsLoadingAssets(true);
    try {
      const res = await apiClient.listDatasetAssets(datasetId);
      setAvailableAssets(res.assets || []);
    } catch (err) {
      console.error('Failed to load dataset assets:', err);
      setAvailableAssets([]);
    } finally {
      setIsLoadingAssets(false);
    }
  };

  useEffect(() => {
    checkHealth();
    refreshSavedDatasets();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (currentDataset?.dataset_id) {
      refreshAssets(currentDataset.dataset_id);
    } else {
      setAvailableAssets([]);
    }
  }, [currentDataset?.dataset_id]);

  return (
    <DatasetContext.Provider
      value={{
        currentDataset,
        setCurrentDataset,
        savedDatasets,
        refreshSavedDatasets,
        isLoadingDatasets,
        availableAssets,
        setAvailableAssets,
        isLoadingAssets,
        refreshAssets,
        apiHealth,
        checkHealth,
      }}
    >
      {children}
    </DatasetContext.Provider>
  );
};

export const useDataset = (): DatasetContextType => {
  const context = useContext(DatasetContext);
  if (!context) {
    throw new Error('useDataset must be used within a DatasetProvider');
  }
  return context;
};
