from fastapi import FastAPI, APIRouter, Depends, UploadFile, status, Request
from fastapi.responses import JSONResponse
import os
from helpers.config import get_settings, Settings
from controllers import DataController, ProjectController, ProcessController
import aiofiles
from models import ResponseSignal
import logging
from .schemes.data import ProcessRequest, DeleteRequest
from models.ProjectModel import ProjectModel
from models.ChunkModel import ChunkModel
from models.AssetModel import AssetModel
from models.db_schemes import DataChunk, Asset
from models.enums.AssetTypeEnum import AssetTypeEnum
from typing import List

logger = logging.getLogger('uvicorn.error')

data_router = APIRouter(
    prefix='/api/v1/data',
    tags=["api_v1", "data"]
)

@data_router.post('/upload/{project_id}')
async def upload_data(request: Request, project_id: str, files: List[UploadFile],
                      app_settings: Settings=Depends(get_settings)):
    
    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
    asset_model = await AssetModel.create_instance(db_client=request.app.db_client)
    
    project = await project_model.get_project_or_create_one(project_id=project_id)
    data_controller = DataController()
    
    file_ids = []
    
    for file in files:
        is_valid, result_signal = data_controller.validate_uploaded_file(file=file)
        
        if not is_valid:
            logger.error(f"This file is not valid: {file.filename}")
            continue
            
        file_path, file_id = data_controller.generate_unique_filepath(
            orig_file_name=file.filename,
            project_id=project_id
        )
           
        try:
            async with aiofiles.open(file_path, "wb") as f:
                while chunk := await file.read(app_settings.FILE_DEFAULT_CHUNK_SIZE):
                    await f.write(chunk)
        except Exception as e:
            
            logger.error(f"Error while uploading file: {e}")
            continue
            
        # store the assets into the database
        asset_resource = Asset(
            asset_project_id=project.id,
            asset_type=AssetTypeEnum.FILE.value, # check
            asset_name=file_id,
            asset_size=os.path.getsize(file_path),
            file_path=file_path
            )
        
        asset_record = await asset_model.create_asset(asset=asset_resource)
        
        file_ids.append(str(asset_record.id))
        
    return JSONResponse(
        content={
            'signal': ResponseSignal.FILE_UPLOAD_SUCCESS.value,
            'file_ids': file_ids
        }
    )
    
    
    
    
@data_router.get('/get_uploaded_files/{project_id}')
async def get_uploaded_data(request: Request, project_id: str):
    
    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
    asset_model = await AssetModel.create_instance(db_client=request.app.db_client)

    project = await project_model.get_project_or_create_one(project_id=project_id)
    
    project_files = await asset_model.get_all_project_assets(
            asset_project_id=project.id,
            asset_type=AssetTypeEnum.FILE.value
        )
    if len(project_files) == 0:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "signal": ResponseSignal.NO_FILES_ERROR.value,
            }
        )
    
    file_ids = [record.asset_name for record in project_files]
    file_paths = [record.file_path for record in project_files]
    
    return JSONResponse(
        content={
            'signal': ResponseSignal.FILE_RETURNED_SUCCESS.value,
            'file_names': file_ids,
            'file_paths': file_paths,
        }
    )
    
    
@data_router.post('/process/{project_id}')
async def process_endpoint(request: Request, project_id: str, process_request: ProcessRequest):
    
    # file_id = process_request.file_id
    chunk_size = process_request.chunk_size
    overlap_size = process_request.overlap_size
    do_reset = process_request.do_reset

    
    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
    project = await project_model.get_project_or_create_one(project_id=project_id)
    asset_model = await AssetModel.create_instance(db_client=request.app.db_client)
    
    project_files_ids = {}
    
    if process_request.file_id:
        asset_record = await asset_model.get_asset_record(
            asset_project_id=project.id,
            asset_name=process_request.file_id
        )
        
        if asset_record is None:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    'signal': ResponseSignal.FILE_ID_ERROR.value,
                }
            )
        
        project_files_ids = {
            asset_record.id: asset_record.asset_name
        }
        
    else:
        project_files = await asset_model.get_all_project_assets(
            asset_project_id=project.id,
            asset_type=AssetTypeEnum.FILE.value
        )
        
        project_files_ids = {
            record.id: record.asset_name
            for record in project_files
        }
        
    
    if len(project_files_ids) == 0:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "signal": ResponseSignal.NO_FILES_ERROR.value,
            }
        )
        
    process_controller = ProcessController(project_id=project_id)

    no_records = 0
    no_files = 0

    chunk_model = await ChunkModel.create_instance(db_client=request.app.db_client)
    
    if do_reset:
        _ = await chunk_model.delete_chunks_by_project_id(
            project_id=project.id
        )
        
    for asset_id, file_id in project_files_ids.items():
        
        # get file content
        file_content = process_controller.get_file_content(file_id=file_id)
        
        if file_content is None:
            logger.error(f"Error while processing file: {file_id}")
            continue
        
        # convert them into chunks
        file_chunks = process_controller.process_file_content(
            file_content=file_content,
            file_id=file_id,
            chunk_size=chunk_size,
            overlap_size=overlap_size
        )
        
        if file_chunks is None or len(file_chunks) == 0:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "signal": ResponseSignal.PROCESSING_FAILED.value
                }
            )
        
        file_chunks_records = [
            DataChunk(
                chunk_text=chunk.page_content,
                chunk_metadata=chunk.metadata,
                chunk_order=i+1,
                chunk_project_id=project.id, # file_id
                chunk_asset_id=asset_id
            )
            for i, chunk in enumerate(file_chunks)
        ]
        
        no_records += await chunk_model.insert_many_chunks(chunks=file_chunks_records)
        no_files += 1
        
    return JSONResponse(
        content={
            'signal': ResponseSignal.PROCESSING_SUCCESS.value,
            'inserted_chunks': no_records,
            "processed_files": no_files
        }
    )
    
    
@data_router.delete('/delete_document/{project_id}')
async def delete_document(request: Request, project_id: str, delete_request: DeleteRequest):
    file_ids = delete_request.file_ids
    
    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
    asset_model = await AssetModel.create_instance(db_client=request.app.db_client)
    chunk_model = await ChunkModel.create_instance(db_client=request.app.db_client)
    
    project = await project_model.get_project_or_create_one(project_id=project_id)
    
    deleted_files = {
        'file_names': [],
        'file_paths': []
    }
    
    for file_id in file_ids:
        # Find the files in the assets
        asset_record = await asset_model.get_asset_record(
            asset_project_id=project.id,
            asset_name=file_id
        )

        if asset_record is None:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    'signal': ResponseSignal.ASSET_NOT_FOUND_ERROR.value
                }
            )        
        
        # Delete this file from assets by asset id
        asset_deletion_result = await asset_model.delete_asset_by_id(asset_id=asset_record.id)
        
        if asset_deletion_result:
            deleted_files['file_names'].append(asset_record.asset_name)
            
            if os.path.exists(asset_record.file_path):
                deleted_files['file_paths'].append(asset_record.file_path)
                os.remove(asset_record.file_path)
            
            
    
        # Delete the file chunks by asset id
        _ = await chunk_model.delete_chunks_by_asset_id(asset_id=asset_record.id)
        
            
        
    if len(deleted_files['file_names']) > 0:
        return JSONResponse(
            content={
                'signal': ResponseSignal.ASSET_DELETION_SUCCESS.value,
                'file_names': deleted_files['file_names'],
                'file_path': deleted_files['file_paths'],
            }
        )
    
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            'signal': ResponseSignal.DELETION_ERROR.value
        }
    )